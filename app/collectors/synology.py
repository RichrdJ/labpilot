"""Synology DSM collector using the DSM Web API (entry.cgi)."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import SynologyConfig
from .base import Collector, CollectorError

log = logging.getLogger(__name__)


def _num(v: Any, default: float = 0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


class SynologyCollector(Collector):
    name = "synology"
    label = "Synology"

    def __init__(self, cfg: SynologyConfig) -> None:
        self.cfg = cfg
        self._client = httpx.AsyncClient(base_url=cfg.url, verify=cfg.verify_ssl, timeout=15)
        self._sid: str | None = None

    async def _login(self) -> None:
        r = await self._client.get(
            "/webapi/auth.cgi",
            params={
                "api": "SYNO.API.Auth",
                "version": 6,
                "method": "login",
                "account": self.cfg.user,
                "passwd": self.cfg.password,
                "session": "LabPilot",
                "format": "sid",
            },
        )
        data = r.json()
        if not data.get("success"):
            raise CollectorError(f"DSM login failed (code {data.get('error', {}).get('code')})")
        self._sid = data["data"]["sid"]

    async def _call(self, api: str, method: str, version: int = 1, **params: Any) -> dict[str, Any]:
        if not self._sid:
            await self._login()
        for attempt in range(2):
            r = await self._client.get(
                "/webapi/entry.cgi",
                params={"api": api, "version": version, "method": method, "_sid": self._sid, **params},
            )
            data = r.json()
            if data.get("success"):
                return data.get("data", {})
            code = data.get("error", {}).get("code")
            if code in (105, 106, 107, 119) and attempt == 0:  # session expired / invalid
                await self._login()
                continue
            raise CollectorError(f"{api}.{method} failed (code {code})")
        return {}

    async def _try(self, api: str, method: str, version: int = 1, **params: Any) -> dict[str, Any] | None:
        try:
            return await self._call(api, method, version, **params)
        except CollectorError as exc:
            log.debug("synology optional call failed: %s", exc)
            return None

    async def collect(self) -> dict[str, Any]:
        try:
            info = await self._try("SYNO.Core.System", "info") or {}
            util = await self._call("SYNO.Core.System.Utilization", "get")
            storage = await self._call("SYNO.Storage.CGI.Storage", "load_info")
        except httpx.HTTPError as exc:
            raise CollectorError(str(exc)) from exc

        cpu = util.get("cpu", {})
        cpu_pct = _num(cpu.get("user_load")) + _num(cpu.get("system_load")) + _num(cpu.get("other_load"))
        mem_pct = _num(util.get("memory", {}).get("real_usage"))

        volumes = []
        for v in storage.get("volumes", []):
            size = v.get("size", {})
            volumes.append(
                {
                    "name": v.get("display_name") or v.get("vol_path") or v.get("id"),
                    "capacity": _num(size.get("total")),
                    "used": _num(size.get("used")),
                    "status": v.get("status", "unknown"),
                    "fs": v.get("fs_type"),
                }
            )
        disks = []
        for d in storage.get("disks", []):
            disks.append(
                {
                    "id": d.get("id"),
                    "name": d.get("longName") or d.get("name") or d.get("id"),
                    "model": (d.get("model") or "").strip(),
                    "temp": d.get("temp"),
                    "status": d.get("smart_status") or d.get("status") or "unknown",
                    "size": _num(d.get("size_total")),
                }
            )

        ups_raw = await self._try("SYNO.Core.ExternalDevice.UPS", "get") or {}
        ups = None
        if ups_raw:
            ups = {
                "status": ups_raw.get("status") or ups_raw.get("ups_status") or "unknown",
                "charge": ups_raw.get("charge") or ups_raw.get("battery_charge"),
                "model": ups_raw.get("model"),
            }

        tasks_raw = await self._try("SYNO.Backup.Task", "list", additional='["last_bkp_result","last_bkp_time"]') or {}
        backups = []
        for t in tasks_raw.get("task_list", []):
            backups.append(
                {
                    "name": t.get("name"),
                    "status": t.get("last_bkp_result") or t.get("status") or t.get("state") or "unknown",
                    "last": t.get("last_bkp_time"),
                }
            )

        return {
            "model": info.get("model", "Synology NAS"),
            "dsm": info.get("firmware_ver", ""),
            "temp": info.get("sys_temp"),
            "uptime": info.get("up_time"),
            "cpu_pct": round(cpu_pct, 1),
            "mem_pct": round(mem_pct, 1),
            "volumes": volumes,
            "disks": disks,
            "ups": ups,
            "backups": backups,
        }

    async def close(self) -> None:
        await self._client.aclose()
