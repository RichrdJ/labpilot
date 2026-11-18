"""UniFi OS (UDM / UDM Pro / UDM SE) collector using the Network application API."""
from __future__ import annotations

from typing import Any

import httpx

from ..config import UniFiConfig
from .base import Collector, CollectorError


class UniFiCollector(Collector):
    name = "unifi"
    label = "UniFi"

    def __init__(self, cfg: UniFiConfig) -> None:
        self.cfg = cfg
        headers = {"Accept": "application/json"}
        if cfg.api_key:
            headers["X-API-KEY"] = cfg.api_key
        self._client = httpx.AsyncClient(base_url=cfg.url, verify=cfg.verify_ssl, timeout=15, headers=headers)
        self._logged_in = False

    @property
    def _base(self) -> str:
        return f"/proxy/network/api/s/{self.cfg.site}"

    async def _login(self) -> None:
        if self.cfg.api_key:
            return
        r = await self._client.post(
            "/api/auth/login",
            json={"username": self.cfg.user, "password": self.cfg.password, "rememberMe": True},
        )
        if r.status_code != 200:
            raise CollectorError(f"UniFi login failed (HTTP {r.status_code})")
        csrf = r.headers.get("x-csrf-token") or r.headers.get("X-Updated-Csrf-Token")
        if csrf:
            self._client.headers["X-CSRF-Token"] = csrf
        self._logged_in = True

    async def _req(self, method: str, path: str, **kw: Any) -> Any:
        if not self.cfg.api_key and not self._logged_in:
            await self._login()
        for attempt in range(2):
            r = await self._client.request(method, f"{self._base}{path}", **kw)
            if r.status_code == 401 and attempt == 0 and not self.cfg.api_key:
                self._logged_in = False
                await self._login()
                continue
            if r.status_code >= 400:
                raise CollectorError(f"UniFi {path} HTTP {r.status_code}")
            new_csrf = r.headers.get("X-Updated-Csrf-Token")
            if new_csrf:
                self._client.headers["X-CSRF-Token"] = new_csrf
            return r.json().get("data", [])
        return []

    async def collect(self) -> dict[str, Any]:
        try:
            health = await self._req("GET", "/stat/health")
            clients = await self._req("GET", "/stat/sta")
            devices = await self._req("GET", "/stat/device")
            networks = await self._req("GET", "/rest/networkconf")
            try:
                alarms = await self._req("GET", "/stat/alarm", params={"archived": "false"})
            except CollectorError:
                alarms = []
            try:
                blocked = await self._req("GET", "/rest/user", params={"blocked": "true"})
            except CollectorError:
                blocked = []
        except httpx.HTTPError as exc:
            raise CollectorError(str(exc)) from exc

        wan = {"status": "unknown"}
        for sub in health:
            if sub.get("subsystem") == "wan":
                wan = {
                    "status": sub.get("status", "unknown"),
                    "ip": sub.get("wan_ip"),
                    "isp": sub.get("isp_name") or sub.get("isp_organization"),
                    "rx_bps": (sub.get("rx_bytes-r") or 0) * 8,
                    "tx_bps": (sub.get("tx_bytes-r") or 0) * 8,
                    "gateway": sub.get("gw_name"),
                }
            if sub.get("subsystem") == "www":
                wan["latency"] = sub.get("latency")
                wan["uptime"] = sub.get("uptime")
                wan["speedtest_down"] = sub.get("xput_down")
                wan["speedtest_up"] = sub.get("xput_up")

        net_names = {n.get("_id"): n.get("name") for n in networks}
        out_clients = []
        for c in clients:
            out_clients.append(
                {
                    "mac": (c.get("mac") or "").lower(),
                    "name": c.get("name") or c.get("hostname") or c.get("oui") or c.get("mac"),
                    "hostname": c.get("hostname"),
                    "vendor": c.get("oui"),
                    "ip": c.get("ip"),
                    "network": c.get("network") or net_names.get(c.get("network_id")) or "?",
                    "wired": bool(c.get("is_wired")),
                    "rx_bytes": c.get("rx_bytes", 0),
                    "tx_bytes": c.get("tx_bytes", 0),
                    "rx_rate": c.get("rx_bytes-r", 0),
                    "tx_rate": c.get("tx_bytes-r", 0),
                    "first_seen": c.get("first_seen"),
                    "last_seen": c.get("last_seen"),
                    "signal": c.get("signal"),
                    "known": bool(c.get("name") or c.get("noted")),
                    "blocked": False,
                }
            )
        for b in blocked:
            out_clients.append(
                {
                    "mac": (b.get("mac") or "").lower(),
                    "name": b.get("name") or b.get("hostname") or b.get("mac"),
                    "vendor": b.get("oui"),
                    "ip": None,
                    "network": "-",
                    "wired": False,
                    "rx_bytes": 0,
                    "tx_bytes": 0,
                    "rx_rate": 0,
                    "tx_rate": 0,
                    "first_seen": b.get("first_seen"),
                    "last_seen": b.get("last_seen"),
                    "known": True,
                    "blocked": True,
                }
            )

        out_devices = [
            {
                "name": d.get("name") or d.get("model"),
                "model": d.get("model"),
                "type": d.get("type"),
                "state": "online" if d.get("state") == 1 else "offline",
                "version": d.get("version"),
                "clients": d.get("num_sta", 0),
                "cpu_pct": float((d.get("system-stats") or {}).get("cpu") or 0),
                "mem_pct": float((d.get("system-stats") or {}).get("mem") or 0),
                "temp": next((t.get("value") for t in d.get("temperatures", []) if t.get("value")), None),
                "upgradable": bool(d.get("upgradable")),
            }
            for d in devices
        ]

        out_alarms = [
            {"msg": a.get("msg"), "time": (a.get("time") or 0) / 1000, "key": a.get("key")}
            for a in sorted(alarms, key=lambda a: a.get("time", 0), reverse=True)[:25]
        ]

        return {
            "wan": wan,
            "clients": out_clients,
            "devices": out_devices,
            "networks": [n.get("name") for n in networks if n.get("purpose") in ("corporate", "vlan-only", "guest")],
            "alarms": out_alarms,
        }

    async def action(self, kind: str, target: str, **kwargs: Any) -> str:
        cmds = {"block": "block-sta", "unblock": "unblock-sta", "reconnect": "kick-sta"}
        if kind not in cmds:
            raise CollectorError(f"Unknown action {kind}")
        await self._req("POST", "/cmd/stamgr", json={"cmd": cmds[kind], "mac": target})
        return f"{kind} sent for {target}"

    async def close(self) -> None:
        await self._client.aclose()
