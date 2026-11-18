"""Veeam Backup & Replication collector (REST API, v12+ on port 9419)."""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import httpx

from ..config import VeeamConfig
from .base import Collector, CollectorError


def _ts(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


class VeeamCollector(Collector):
    name = "veeam"
    label = "Veeam"

    def __init__(self, cfg: VeeamConfig) -> None:
        self.cfg = cfg
        self._client = httpx.AsyncClient(
            base_url=cfg.url,
            verify=cfg.verify_ssl,
            timeout=20,
            headers={"x-api-version": cfg.api_version, "Accept": "application/json"},
        )
        self._token: str | None = None
        self._expires = 0.0

    async def _auth(self) -> None:
        r = await self._client.post(
            "/api/oauth2/token",
            data={"grant_type": "password", "username": self.cfg.user, "password": self.cfg.password},
        )
        if r.status_code != 200:
            raise CollectorError(f"Veeam login failed (HTTP {r.status_code})")
        body = r.json()
        self._token = body["access_token"]
        self._expires = time.time() + int(body.get("expires_in", 900)) - 60

    async def _get(self, path: str, **params: Any) -> Any:
        if not self._token or time.time() > self._expires:
            await self._auth()
        r = await self._client.get(path, params=params, headers={"Authorization": f"Bearer {self._token}"})
        if r.status_code == 401:
            await self._auth()
            r = await self._client.get(path, params=params, headers={"Authorization": f"Bearer {self._token}"})
        if r.status_code >= 400:
            raise CollectorError(f"Veeam {path} HTTP {r.status_code}")
        return r.json()

    async def collect(self) -> dict[str, Any]:
        try:
            states = await self._get("/api/v1/jobs/states", limit=200)
            sessions = await self._get("/api/v1/sessions", limit=25, orderColumn="CreationTime", orderAsc="false")
            try:
                repos = await self._get("/api/v1/backupInfrastructure/repositories/states", limit=100)
            except CollectorError:
                repos = {"data": []}
        except httpx.HTTPError as exc:
            raise CollectorError(str(exc)) from exc

        jobs = []
        for j in states.get("data", []):
            jobs.append(
                {
                    "id": j.get("id"),
                    "name": j.get("name"),
                    "type": j.get("type"),
                    "status": (j.get("status") or "").lower(),  # running / inactive / disabled
                    "last_result": (j.get("lastResult") or "None").lower(),  # success / warning / failed / none
                    "last_run": _ts(j.get("lastRun")),
                    "next_run": _ts(j.get("nextRun")),
                    "objects": j.get("objectsCount"),
                    "repository": j.get("repositoryName"),
                    "progress": j.get("progressPercent"),
                }
            )
        out_sessions = []
        for s in sessions.get("data", []):
            res = s.get("result") or {}
            start, end = _ts(s.get("creationTime")), _ts(s.get("endTime"))
            out_sessions.append(
                {
                    "name": s.get("name"),
                    "state": (s.get("state") or "").lower(),
                    "result": (res.get("result") or "none").lower(),
                    "message": res.get("message"),
                    "start": start,
                    "end": end,
                    "duration": (end - start) if start and end else None,
                }
            )
        out_repos = []
        for rp in repos.get("data", []):
            cap = float(rp.get("capacityGB") or 0) * 1024**3
            free = float(rp.get("freeGB") or 0) * 1024**3
            out_repos.append({"name": rp.get("name"), "capacity": cap, "free": free, "type": rp.get("type")})

        return {"jobs": jobs, "sessions": out_sessions, "repositories": out_repos}

    async def action(self, kind: str, target: str, **kwargs: Any) -> str:
        if kind not in ("start", "stop"):
            raise CollectorError(f"Unknown action {kind}")
        if not self._token or time.time() > self._expires:
            await self._auth()
        r = await self._client.post(
            f"/api/v1/jobs/{target}/{kind}",
            json={},
            headers={"Authorization": f"Bearer {self._token}"},
        )
        if r.status_code >= 400:
            raise CollectorError(f"Veeam job {kind} failed (HTTP {r.status_code})")
        return f"Job {kind} requested"

    async def close(self) -> None:
        await self._client.aclose()
