"""Polling engine: runs collectors, keeps history, correlates sources and derives insights."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any

from .collectors.base import Collector, CollectorError
from .config import Settings

log = logging.getLogger("labpilot.engine")

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


class Engine:
    def __init__(self, settings: Settings, collectors: list[Collector]) -> None:
        self.settings = settings
        self.collectors = {c.name: c for c in collectors}
        self.data: dict[str, dict[str, Any]] = {}
        self.status: dict[str, dict[str, Any]] = {
            c.name: {"label": c.label, "ok": None, "error": None, "updated": None, "latency_ms": None}
            for c in collectors
        }
        self.history: dict[str, deque] = {}
        self.events: deque = deque(maxlen=200)
        self.snapshot: dict[str, Any] = {}
        self.version = 0
        self._cond = asyncio.Condition()
        self._task: asyncio.Task | None = None
        self._prev: dict[str, Any] = {}

    # -- lifecycle -----------------------------------------------------------
    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        for c in self.collectors.values():
            await c.close()

    async def _loop(self) -> None:
        while True:
            try:
                await self.poll()
            except Exception:  # never let the loop die
                log.exception("poll failed")
            await asyncio.sleep(self.settings.poll_interval)

    async def _run(self, c: Collector) -> None:
        t0 = time.perf_counter()
        st = self.status[c.name]
        try:
            self.data[c.name] = await asyncio.wait_for(c.collect(), timeout=45)
            if st["ok"] is False:
                self.event("success", c.name, f"{c.label} is weer bereikbaar")
            st.update(ok=True, error=None, updated=time.time())
        except (TimeoutError, CollectorError, Exception) as exc:  # noqa: BLE001
            msg = str(exc) or exc.__class__.__name__
            if st["ok"] is not False:
                self.event("critical", c.name, f"{c.label} niet bereikbaar: {msg}")
            st.update(ok=False, error=msg)
            log.warning("%s collect failed: %s", c.name, msg)
        st["latency_ms"] = round((time.perf_counter() - t0) * 1000)

    async def poll(self) -> None:
        await asyncio.gather(*(self._run(c) for c in self.collectors.values()))
        self._record_history()
        self._detect_changes()
        self.snapshot = self._build_snapshot()
        async with self._cond:
            self.version += 1
            self._cond.notify_all()

    async def wait_for_update(self, version: int, timeout: float = 25) -> int:
        async with self._cond:
            try:
                await asyncio.wait_for(self._cond.wait_for(lambda: self.version != version), timeout)
            except TimeoutError:
                pass
            return self.version

    # -- events / history ----------------------------------------------------
    def event(self, level: str, source: str, msg: str) -> None:
        self.events.appendleft({"time": time.time(), "level": level, "source": source, "msg": msg})

    def _push(self, key: str, value: float | None) -> None:
        if value is None:
            return
        dq = self.history.setdefault(key, deque(maxlen=self.settings.history_points))
        dq.append((round(time.time()), round(float(value), 2)))

    def _record_history(self) -> None:
        e, s, u = self.data.get("esxi"), self.data.get("synology"), self.data.get("unifi")
        if e and e.get("hosts"):
            hosts = e["hosts"]
            self._push("esxi_cpu", sum(h["cpu_pct"] for h in hosts) / len(hosts))
            self._push("esxi_mem", sum(h["mem_pct"] for h in hosts) / len(hosts))
        if s:
            self._push("nas_cpu", s.get("cpu_pct"))
            self._push("nas_mem", s.get("mem_pct"))
        if u:
            self._push("wan_rx", u["wan"].get("rx_bps"))
            self._push("wan_tx", u["wan"].get("tx_bps"))
            self._push("clients", len([c for c in u["clients"] if not c.get("blocked")]))
            self._push("latency", u["wan"].get("latency"))

    def _detect_changes(self) -> None:
        e, u, v = self.data.get("esxi"), self.data.get("unifi"), self.data.get("veeam")
        prev = self._prev
        if e:
            states = {vm["name"]: vm["state"] for vm in e["vms"]}
            for name, st in states.items():
                old = prev.get("vm", {}).get(name)
                if old and old != st:
                    self.event("info", "esxi", f"VM {name}: {old} → {st}")
            prev["vm"] = states
        if u:
            macs = {c["mac"]: c for c in u["clients"]}
            if "macs" in prev:
                for mac, c in macs.items():
                    if mac not in prev["macs"] and not c["blocked"]:
                        lvl = "info" if c.get("known") else "warning"
                        self.event(lvl, "unifi", f"Nieuw op netwerk: {c['name']} ({c['ip']}, {c['network']})")
            prev["macs"] = set(macs)
        if v:
            results = {j["id"]: (j["name"], j["last_result"]) for j in v["jobs"]}
            for jid, (name, res) in results.items():
                old = prev.get("jobs", {}).get(jid)
                if old and old[1] != res:
                    lvl = {"failed": "critical", "warning": "warning"}.get(res, "success")
                    self.event(lvl, "veeam", f"Job {name}: {res}")
            prev["jobs"] = results

    # -- derived data --------------------------------------------------------
    def _correlate(self) -> list[dict[str, Any]]:
        """Join ESXi VMs with UniFi clients (by MAC) and Veeam jobs (best effort)."""
        e, u = self.data.get("esxi"), self.data.get("unifi")
        if not e:
            return []
        by_mac = {c["mac"]: c for c in (u or {}).get("clients", [])}
        out = []
        for vm in e["vms"]:
            client = next((by_mac[m] for m in vm.get("macs", []) if m in by_mac), None)
            out.append(
                {
                    "vm": vm["name"],
                    "id": vm["id"],
                    "state": vm["state"],
                    "network": client["network"] if client else None,
                    "ip": (client or {}).get("ip") or vm.get("ip"),
                    "rx_rate": (client or {}).get("rx_rate", 0),
                    "tx_rate": (client or {}).get("tx_rate", 0),
                    "seen": client is not None,
                }
            )
        return out

    def _insights(self, correlation: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cfg = self.settings
        out: list[dict[str, Any]] = []
        now = time.time()

        def add(sev: str, src: str, title: str, detail: str = "", action: dict | None = None) -> None:
            out.append({"severity": sev, "source": src, "title": title, "detail": detail, "action": action})

        for name, st in self.status.items():
            if st["ok"] is False:
                add("critical", name, f"{st['label']} niet bereikbaar", st["error"] or "")

        e = self.data.get("esxi")
        if e:
            for h in e["hosts"]:
                if h["mem_pct"] > 90:
                    add("warning", "esxi", f"Geheugen {h['name']} op {h['mem_pct']:.0f}%")
                if h["cpu_pct"] > 90:
                    add("warning", "esxi", f"CPU {h['name']} op {h['cpu_pct']:.0f}%")
            for ds in e["datastores"]:
                pct = 100 * ds["free"] / ds["capacity"] if ds["capacity"] else 100
                if pct < cfg.low_space_pct:
                    add("warning", "esxi", f"Datastore {ds['name']} bijna vol", f"Nog {pct:.0f}% vrij")
            old = [
                (vm["name"], (now - sn["created"]) / 86400)
                for vm in e["vms"]
                for sn in vm["snapshots"]
                if now - sn["created"] > cfg.snapshot_max_age_days * 86400
            ]
            if old:
                names = sorted({n for n, _ in old})
                oldest = max(d for _, d in old)
                add("warning", "esxi", f"{len(old)} snapshot(s) ouder dan {cfg.snapshot_max_age_days} dagen",
                    f"{', '.join(names)} · oudste {oldest:.0f} dagen")

        s = self.data.get("synology")
        if s:
            for vol in s["volumes"]:
                free = 100 * (1 - vol["used"] / vol["capacity"]) if vol["capacity"] else 100
                if free < cfg.low_space_pct:
                    add("warning", "synology", f"{vol['name']} bijna vol", f"Nog {free:.0f}% vrij")
                if vol["status"] not in ("normal", "unknown"):
                    add("critical", "synology", f"{vol['name']} status: {vol['status']}")
            for d in s["disks"]:
                if str(d["status"]).lower() not in ("normal", "unknown"):
                    add("warning", "synology", f"{d['name']} SMART: {d['status']}", d["model"])
            ups = s.get("ups")
            if ups and str(ups.get("status", "")).upper().startswith("OB"):
                add("critical", "synology", "UPS draait op batterij", f"Lading {ups.get('charge')}%")
            for b in s.get("backups", []):
                if str(b["status"]).lower() in ("failed", "error", "partial"):
                    add("warning", "synology", f"Hyper Backup {b['name']} mislukt")

        u = self.data.get("unifi")
        if u:
            if u["wan"].get("status") not in ("ok", "unknown"):
                add("critical", "unifi", "WAN-verbinding verstoord", str(u["wan"].get("status")))
            ips = [a for a in u["alarms"] if "IPS" in (a.get("key") or "") and now - a["time"] < 86400]
            for c in u["clients"]:
                if c["blocked"] or c.get("known") or not c.get("first_seen"):
                    continue
                if now - c["first_seen"] < 86400:
                    flagged = any(c["ip"] and c["ip"] in (a["msg"] or "") for a in ips)
                    add(
                        "critical" if flagged else "warning",
                        "unifi",
                        f"Onbekend apparaat: {c['name']}",
                        f"{c.get('vendor') or 'Onbekende fabrikant'} · {c['ip']} · {c['network']}"
                        + (" · triggerde IPS-melding" if flagged else ""),
                        {"source": "unifi", "kind": "block", "target": c["mac"], "label": "Blokkeren"},
                    )
            if ips:
                add("info", "unifi", f"{len(ips)} IPS-melding(en) in 24 uur", ips[0]["msg"][:90])
            for d in u["devices"]:
                if d["state"] != "online":
                    add("critical", "unifi", f"{d['name']} offline")
                elif d.get("upgradable"):
                    add("info", "unifi", f"Firmware-update voor {d['name']}")

        v = self.data.get("veeam")
        if v:
            for j in v["jobs"]:
                if j["last_result"] == "failed":
                    add("critical", "veeam", f"Veeam-job {j['name']} mislukt", j.get("repository") or "",
                        {"source": "veeam", "kind": "start", "target": j["id"], "label": "Opnieuw starten"})
                elif j["last_result"] == "warning":
                    add("warning", "veeam", f"Veeam-job {j['name']} met waarschuwing")
                if j["last_run"] and now - j["last_run"] > 36 * 3600 and j["status"] != "disabled":
                    add("warning", "veeam", f"{j['name']} draaide > 36 uur niet")
            for r in v["repositories"]:
                pct = 100 * r["free"] / r["capacity"] if r["capacity"] else 100
                if pct < cfg.low_space_pct:
                    add("warning", "veeam", f"Repository {r['name']} bijna vol", f"Nog {pct:.0f}% vrij")

        if u and correlation:
            for c in correlation:
                if c["state"] == "on" and not c["seen"]:
                    add("info", "esxi", f"VM {c['vm']} staat aan maar is niet zichtbaar op het netwerk")

        out.sort(key=lambda i: SEVERITY_ORDER[i["severity"]])
        return out

    def _summary(self) -> dict[str, Any]:
        e, s, u, v = (self.data.get(k) for k in ("esxi", "synology", "unifi", "veeam"))
        out: dict[str, Any] = {}
        if e:
            out["vms_on"] = sum(1 for vm in e["vms"] if vm["state"] == "on")
            out["vms_total"] = len(e["vms"])
        if s:
            cap = sum(x["capacity"] for x in s["volumes"])
            used = sum(x["used"] for x in s["volumes"])
            out["nas_free"] = cap - used
            out["nas_used_pct"] = round(100 * used / cap, 1) if cap else 0
        if u:
            out["clients"] = len([c for c in u["clients"] if not c["blocked"]])
            out["wan_rx"] = u["wan"].get("rx_bps")
            out["wan_tx"] = u["wan"].get("tx_bps")
        if v:
            runs = [j["last_run"] for j in v["jobs"] if j["last_run"] and j["last_result"] in ("success", "warning")]
            out["last_backup"] = max(runs) if runs else None
            out["jobs_ok"] = sum(1 for j in v["jobs"] if j["last_result"] == "success")
            out["jobs_total"] = len(v["jobs"])
        return out

    def _build_snapshot(self) -> dict[str, Any]:
        correlation = self._correlate()
        insights = self._insights(correlation)
        crit = sum(1 for i in insights if i["severity"] == "critical")
        warn = sum(1 for i in insights if i["severity"] == "warning")
        return {
            "meta": {
                "title": self.settings.title,
                "demo": self.settings.demo_active,
                "actions": self.settings.actions_enabled or self.settings.demo_active,
                "poll_interval": self.settings.poll_interval,
                "generated": time.time(),
                "health": "critical" if crit else ("warning" if warn else "ok"),
            },
            "status": self.status,
            "summary": self._summary(),
            "esxi": self.data.get("esxi"),
            "synology": self.data.get("synology"),
            "unifi": self.data.get("unifi"),
            "veeam": self.data.get("veeam"),
            "correlation": correlation,
            "insights": insights,
            "events": list(self.events)[:60],
            "history": {k: list(v) for k, v in self.history.items()},
        }
