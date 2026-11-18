"""Realistic, slowly drifting demo data so the UI can be explored without real hardware."""
from __future__ import annotations

import math
import random
import time
from typing import Any

from .base import Collector, CollectorError

GB = 1024**3
TB = 1024**4
DAY = 86400


def _wave(period: float, amp: float, base: float, phase: float = 0) -> float:
    t = time.time()
    return base + amp * math.sin(2 * math.pi * t / period + phase) + random.uniform(-amp / 4, amp / 4)


class DemoLab:
    """Shared demo state so cross-source correlations (MAC <-> VM) line up."""

    def __init__(self) -> None:
        now = time.time()
        self.start = now
        self.vms = [
            # name, os, vcpu, mem, state, ip, mac, snapshots(age days)
            ("docker-01", "Debian 12 (64-bit)", 4, 8192, "on", "10.10.20.11", "00:50:56:a1:10:11", []),
            ("homeassistant", "Home Assistant OS", 2, 4096, "on", "10.10.20.12", "00:50:56:a1:10:12", [3]),
            ("pihole", "Debian 12 (64-bit)", 1, 1024, "on", "10.10.20.2", "00:50:56:a1:10:02", []),
            ("veeam-br", "Windows Server 2022", 4, 16384, "on", "10.10.20.20", "00:50:56:a1:10:20", []),
            ("k8s-master", "Ubuntu 24.04 (64-bit)", 2, 4096, "off", None, "00:50:56:a1:10:31", [21]),
            ("k8s-worker-1", "Ubuntu 24.04 (64-bit)", 4, 8192, "off", None, "00:50:56:a1:10:32", [21]),
            ("k8s-worker-2", "Ubuntu 24.04 (64-bit)", 4, 8192, "off", None, "00:50:56:a1:10:33", [21]),
            ("win11-lab", "Windows 11 (64-bit)", 4, 8192, "on", "10.10.20.40", "00:50:56:a1:10:40", [45, 9]),
            ("gitlab", "Ubuntu 22.04 (64-bit)", 4, 8192, "on", "10.10.20.15", "00:50:56:a1:10:15", []),
            ("monitoring", "Debian 12 (64-bit)", 2, 4096, "on", "10.10.20.16", "00:50:56:a1:10:16", []),
            ("dc01", "Windows Server 2022", 2, 4096, "on", "10.10.20.5", "00:50:56:a1:10:05", [2]),
            ("kali", "Debian 12 (64-bit)", 2, 4096, "suspended", None, "00:50:56:a1:10:66", []),
        ]
        self.vm_state = {v[0]: v[4] for v in self.vms}
        self.vm_snaps = {v[0]: [now - d * DAY for d in v[7]] for v in self.vms}
        self.blocked: set[str] = set()
        self.clients = [
            # name, mac, ip, network, wired, vendor, known, first_seen_age_s
            ("Richard-iPhone", "a4:83:e7:12:34:56", "10.10.10.21", "LAN", False, "Apple", True, 90 * DAY),
            ("Richard-EliteBook", "b0:22:7a:aa:bb:cc", "10.10.10.22", "LAN", False, "HP", True, 200 * DAY),
            ("synology-ds920", "00:11:32:ab:cd:ef", "10.10.20.3", "Servers", True, "Synology", True, 400 * DAY),
            ("esxi-01", "3c:ec:ef:11:22:33", "10.10.20.4", "Servers", True, "Supermicro", True, 400 * DAY),
            ("Sonos-Woonkamer", "48:a6:b8:01:02:03", "10.10.30.10", "IoT", False, "Sonos", True, 300 * DAY),
            ("Hue-Bridge", "ec:b5:fa:44:55:66", "10.10.30.11", "IoT", True, "Signify", True, 500 * DAY),
            ("Tado-Bridge", "ec:fa:bc:77:88:99", "10.10.30.12", "IoT", False, "tado", True, 350 * DAY),
            ("LG-OLED", "a8:23:fe:10:20:30", "10.10.30.13", "IoT", True, "LG", True, 250 * DAY),
            ("ESP-Thermo", "e8:db:84:aa:00:01", "10.10.30.20", "IoT", False, "Espressif", True, 120 * DAY),
            ("tuya-3c6a91", "3c:6a:9d:00:91:01", "10.10.30.77", "IoT", False, "Tuya Smart", False, 1800),
            ("Guest-Android", "f2:11:22:33:44:55", "10.10.40.50", "Guest", False, None, False, 7200),
            ("PS5", "bc:33:29:55:66:77", "10.10.10.40", "LAN", True, "Sony", True, 150 * DAY),
        ]
        self.counters: dict[str, float] = {}
        self.jobs = [
            ("a1", "Nightly VMs", "Backup", "success", 2, "NAS-Repo"),
            ("a2", "Domain Controller", "Backup", "success", 1, "NAS-Repo"),
            ("a3", "Gitlab app-aware", "Backup", "warning", 1, "NAS-Repo"),
            ("a4", "Offsite copy", "BackupCopy", "failed", 3, "Wasabi-S3"),
            ("a5", "Home Assistant", "Backup", "success", 1, "NAS-Repo"),
        ]
        self.job_running: dict[str, float] = {}

    # ------------------------------------------------------------------
    def esxi(self) -> dict[str, Any]:
        vms = []
        for name, os_, vcpu, mem, _s, ip, mac, _sn in self.vms:
            state = self.vm_state[name]
            on = state == "on"
            seed = sum(map(ord, name))
            vms.append(
                {
                    "id": f"vm-{seed}",
                    "name": name,
                    "state": state,
                    "os": os_,
                    "vcpu": vcpu,
                    "mem_mb": mem,
                    "cpu_pct": round(max(1, _wave(300 + seed % 200, 12, 8 + seed % 30, seed)), 1) if on else 0,
                    "mem_pct": round(max(5, _wave(900, 4, 40 + seed % 45, seed)), 1) if on else 0,
                    "ip": ip if on else None,
                    "tools": "guestToolsRunning" if on else "guestToolsNotRunning",
                    "macs": [mac],
                    "snapshots": [{"name": f"pre-update-{i + 1}", "created": c} for i, c in enumerate(self.vm_snaps[name])],
                }
            )
        vms.sort(key=lambda v: (v["state"] != "on", v["name"]))
        running = sum(1 for v in vms if v["state"] == "on")
        cpu = min(95, _wave(600, 9, 18 + running * 2.5))
        return {
            "hosts": [
                {
                    "name": "esxi-01.lab.local",
                    "version": "VMware ESXi 8.0.3 build-24280767",
                    "model": "Supermicro X11SCH-F",
                    "cpu_cores": 8,
                    "cpu_pct": round(cpu, 1),
                    "mem_pct": round(min(97, _wave(1200, 2, 48 + running * 2.4)), 1),
                    "mem_total": 128 * GB,
                    "uptime_s": int(time.time() - self.start + 38 * DAY),
                    "state": "connected",
                }
            ],
            "datastores": [
                {"name": "nvme-01", "capacity": 2 * TB, "free": 0.61 * TB, "type": "VMFS"},
                {"name": "ssd-02", "capacity": 1 * TB, "free": 0.12 * TB, "type": "VMFS"},
                {"name": "nas-nfs", "capacity": 8 * TB, "free": 4.2 * TB, "type": "NFS"},
            ],
            "vms": vms,
        }

    def synology(self) -> dict[str, Any]:
        return {
            "model": "DS920+",
            "dsm": "DSM 7.2.2-72806 Update 3",
            "temp": round(_wave(1800, 2, 41)),
            "uptime": int(time.time() - self.start + 61 * DAY),
            "cpu_pct": round(max(2, _wave(400, 8, 14)), 1),
            "mem_pct": round(_wave(2000, 2, 63), 1),
            "volumes": [
                {"name": "Volume 1", "capacity": 21.8 * TB, "used": 13.5 * TB, "status": "normal", "fs": "btrfs"},
                {"name": "Volume 2 (SSD)", "capacity": 0.9 * TB, "used": 0.31 * TB, "status": "normal", "fs": "btrfs"},
            ],
            "disks": [
                {"id": "sata1", "name": "Drive 1", "model": "WD Red Plus 8TB", "temp": 36, "status": "normal", "size": 8 * TB},
                {"id": "sata2", "name": "Drive 2", "model": "WD Red Plus 8TB", "temp": 37, "status": "normal", "size": 8 * TB},
                {"id": "sata3", "name": "Drive 3", "model": "WD Red Plus 8TB", "temp": 38, "status": "normal", "size": 8 * TB},
                {"id": "sata4", "name": "Drive 4", "model": "IronWolf 8TB", "temp": 40, "status": "warning", "size": 8 * TB},
                {"id": "nvme1", "name": "M.2 Drive 1", "model": "Samsung 980 1TB", "temp": 44, "status": "normal", "size": 1 * TB},
            ],
            "ups": {"status": "OL", "charge": 100, "model": "APC Back-UPS 900"},
            "backups": [
                {"name": "HyperBackup → C2", "status": "success", "last": time.time() - 7 * 3600},
                {"name": "Foto's → USB", "status": "success", "last": time.time() - 30 * 3600},
            ],
        }

    def unifi(self) -> dict[str, Any]:
        clients = []
        for name, mac, ip, net, wired, vendor, known, age in self.clients:
            seed = sum(map(ord, mac))
            rate = max(0, _wave(200 + seed % 100, 40_000, 25_000 + (seed % 7) * 15_000, seed))
            if name == "tuya-3c6a91":
                rate = _wave(60, 4_000, 6_000)
            self.counters[mac] = self.counters.get(mac, (seed % 50) * 1e8) + rate * 15
            clients.append(
                {
                    "mac": mac,
                    "name": name,
                    "vendor": vendor,
                    "ip": None if mac in self.blocked else ip,
                    "network": net,
                    "wired": wired,
                    "rx_bytes": int(self.counters[mac] * 0.7),
                    "tx_bytes": int(self.counters[mac] * 0.3),
                    "rx_rate": int(rate * 0.7),
                    "tx_rate": int(rate * 0.3),
                    "first_seen": time.time() - age,
                    "last_seen": time.time(),
                    "signal": None if wired else -40 - seed % 30,
                    "known": known,
                    "blocked": mac in self.blocked,
                }
            )
        for name, _os, _c, _m, _s, ip, mac, _sn in self.vms:
            if self.vm_state[name] != "on":
                continue
            seed = sum(map(ord, mac))
            rate = max(4_000, _wave(300, 80_000, 120_000 + (seed % 5) * 60_000, seed))
            self.counters[mac] = self.counters.get(mac, (seed % 90) * 1e9) + rate * 15
            clients.append(
                {
                    "mac": mac,
                    "name": name,
                    "vendor": "VMware",
                    "ip": ip,
                    "network": "Servers",
                    "wired": True,
                    "rx_bytes": int(self.counters[mac] * 0.5),
                    "tx_bytes": int(self.counters[mac] * 0.5),
                    "rx_rate": int(rate * 0.5),
                    "tx_rate": int(rate * 0.5),
                    "first_seen": time.time() - 100 * DAY,
                    "last_seen": time.time(),
                    "signal": None,
                    "known": True,
                    "blocked": False,
                }
            )
        down = max(1e6, _wave(240, 90e6, 140e6))
        up = max(1e6, _wave(180, 9e6, 18e6, 1))
        return {
            "wan": {
                "status": "ok",
                "ip": "84.104.xx.xx",
                "isp": "Ziggo",
                "rx_bps": down,
                "tx_bps": up,
                "latency": round(max(3, _wave(120, 2, 9))),
                "uptime": int(time.time() - self.start + 12 * DAY),
                "speedtest_down": 1012.4,
                "speedtest_up": 102.1,
                "gateway": "UDM Pro",
            },
            "clients": clients,
            "devices": [
                {"name": "UDM Pro", "model": "UDMPRO", "type": "udm", "state": "online", "version": "4.3.6", "clients": 0,
                 "cpu_pct": round(_wave(300, 6, 22), 1), "mem_pct": round(_wave(900, 2, 58), 1), "temp": 52, "upgradable": False},
                {"name": "USW-24-PoE", "model": "US24P250", "type": "usw", "state": "online", "version": "7.1.26", "clients": 18,
                 "cpu_pct": 0, "mem_pct": 0, "temp": 47, "upgradable": True},
                {"name": "U6-Pro Woonkamer", "model": "U6PRO", "type": "uap", "state": "online", "version": "6.7.31", "clients": 11,
                 "cpu_pct": 0, "mem_pct": 0, "temp": None, "upgradable": False},
                {"name": "U6-Lite Zolder", "model": "U6LITE", "type": "uap", "state": "online", "version": "6.7.31", "clients": 4,
                 "cpu_pct": 0, "mem_pct": 0, "temp": None, "upgradable": False},
            ],
            "networks": ["LAN", "Servers", "IoT", "Guest"],
            "alarms": [
                {"msg": "IPS Alert 2: ET SCAN Suspicious inbound to mySQL port 3306 from 185.224.128.17", "time": time.time() - 1500, "key": "EVT_IPS_IpsAlert"},
                {"msg": "IPS Alert 3: ET POLICY Tuya cloud beacon from 10.10.30.77", "time": time.time() - 1800, "key": "EVT_IPS_IpsAlert"},
                {"msg": "IPS Alert 2: ET SCAN NMAP -sS window 1024 from 45.155.205.233", "time": time.time() - 9000, "key": "EVT_IPS_IpsAlert"},
                {"msg": "Firmware update available for USW-24-PoE", "time": time.time() - 3 * DAY, "key": "EVT_SW_Upgradable"},
            ],
        }

    def veeam(self) -> dict[str, Any]:
        now = time.time()
        today_2am = now - (now % DAY) + 2 * 3600
        jobs = []
        for jid, name, typ, result, idx, repo in self.jobs:
            running_since = self.job_running.get(jid)
            progress = None
            status = "inactive"
            if running_since:
                progress = min(100, int((now - running_since) / 1.2))
                status = "running" if progress < 100 else "inactive"
                if progress >= 100:
                    del self.job_running[jid]
                    result = "success"
            last = (today_2am if today_2am < now else today_2am - DAY) + idx * 900
            jobs.append(
                {
                    "id": jid,
                    "name": name,
                    "type": typ,
                    "status": status,
                    "last_result": result,
                    "last_run": last,
                    "next_run": last + DAY,
                    "objects": idx + 2,
                    "repository": repo,
                    "progress": progress,
                }
            )
        sessions = []
        for d in range(4):
            for _jid, name, _t, result, idx, _r in self.jobs:
                start = today_2am - d * DAY + idx * 900
                if start > now:
                    continue
                res = result if d == 0 else ("success" if (d + idx) % 5 else "warning")
                dur = 600 + (sum(map(ord, name)) % 40) * 60
                sessions.append(
                    {
                        "name": name,
                        "state": "stopped",
                        "result": res,
                        "message": "Failed to upload to S3: 403 Forbidden" if res == "failed" else
                        ("Changed block tracking is disabled for 1 disk" if res == "warning" else "Success"),
                        "start": start,
                        "end": start + dur,
                        "duration": dur,
                    }
                )
        sessions.sort(key=lambda s: s["start"], reverse=True)
        return {
            "jobs": jobs,
            "sessions": sessions[:20],
            "repositories": [
                {"name": "NAS-Repo", "capacity": 8 * TB, "free": 2.9 * TB, "type": "Nfs"},
                {"name": "Wasabi-S3", "capacity": 2 * TB, "free": 1.4 * TB, "type": "AmazonS3Compatible"},
            ],
        }

    # ------------------------------------------------------------------
    def action(self, source: str, kind: str, target: str) -> str:
        if source == "esxi":
            vm = next((v for v in self.vms if f"vm-{sum(map(ord, v[0]))}" == target), None)
            if not vm:
                raise CollectorError("VM not found")
            if kind == "power_on":
                self.vm_state[vm[0]] = "on"
            elif kind in ("shutdown", "power_off"):
                self.vm_state[vm[0]] = "off"
            elif kind != "reboot":
                raise CollectorError(f"Unknown action {kind}")
            return f"{kind.replace('_', ' ')} → {vm[0]}"
        if source == "unifi":
            if kind == "block":
                self.blocked.add(target)
            elif kind == "unblock":
                self.blocked.discard(target)
            elif kind != "reconnect":
                raise CollectorError(f"Unknown action {kind}")
            return f"{kind} → {target}"
        if source == "veeam":
            if kind == "start":
                self.job_running[target] = time.time()
                return "Job started"
            if kind == "stop":
                self.job_running.pop(target, None)
                return "Job stopped"
        raise CollectorError("Unsupported demo action")


class DemoCollector(Collector):
    def __init__(self, lab: DemoLab, name: str, label: str) -> None:
        self.lab = lab
        self.name = name
        self.label = label

    async def collect(self) -> dict[str, Any]:
        return getattr(self.lab, self.name)()

    async def action(self, kind: str, target: str, **kwargs: Any) -> str:
        return self.lab.action(self.name, kind, target)
