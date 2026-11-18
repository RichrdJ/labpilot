"""LabPilot – one pane of glass for ESXi, Synology, UniFi and Veeam."""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from . import __version__
from .collectors.base import Collector, CollectorError
from .config import SCHEMA, SECRET_FIELDS, SECRET_PLACEHOLDER, SOURCE_TYPES, Settings, SettingsStore, build_settings
from .engine import Engine

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("labpilot")
STATIC = Path(__file__).parent / "static"


def build_collectors(cfg: Settings) -> list[Collector]:
    if cfg.demo_active:
        from .collectors.demo import DemoCollector, DemoLab

        lab = DemoLab()
        return [
            DemoCollector(lab, "esxi", "ESXi"),
            DemoCollector(lab, "synology", "Synology"),
            DemoCollector(lab, "unifi", "UniFi"),
            DemoCollector(lab, "veeam", "Veeam"),
        ]
    out: list[Collector] = []
    if cfg.esxi.enabled:
        from .collectors.esxi import ESXiCollector

        out.append(ESXiCollector(cfg.esxi))
    if cfg.synology.enabled:
        from .collectors.synology import SynologyCollector

        out.append(SynologyCollector(cfg.synology))
    if cfg.unifi.enabled:
        from .collectors.unifi import UniFiCollector

        out.append(UniFiCollector(cfg.unifi))
    if cfg.veeam.enabled:
        from .collectors.veeam import VeeamCollector

        out.append(VeeamCollector(cfg.veeam))
    return out


def seed_demo(engine: Engine) -> None:
    """Backfill history and a few events so the demo looks alive from the first second."""
    import math
    import random
    import time
    from collections import deque

    now = time.time()
    n = engine.settings.history_points
    step = engine.settings.poll_interval
    shapes = {
        "esxi_cpu": (32, 9, 0.0), "esxi_mem": (66, 3, 1.0), "nas_cpu": (14, 7, 2.0), "nas_mem": (63, 2, 0.5),
        "wan_rx": (140e6, 90e6, 0.3), "wan_tx": (18e6, 9e6, 1.7), "clients": (27, 2, 0.9), "latency": (9, 2, 0.1),
    }
    for key, (base, amp, ph) in shapes.items():
        dq = deque(maxlen=n)
        for i in range(n):
            t = now - (n - i) * step
            v = base + amp * math.sin(i / 9 + ph) + amp * 0.5 * math.sin(i / 3.1 + ph * 2) + random.uniform(-amp, amp) * 0.25
            if key.startswith("wan") and random.random() < 0.05:
                v *= 1.8
            dq.append((round(t), round(max(0.0, v), 2)))
        engine.history[key] = dq
    seeded = [
        (5400, "success", "veeam", "Job Nightly VMs: success"),
        (4200, "critical", "veeam", "Job Offsite copy: failed"),
        (2700, "info", "esxi", "VM k8s-worker-2: on → off"),
        (1800, "warning", "unifi", "Nieuw op netwerk: tuya-3c6a91 (10.10.30.77, IoT)"),
        (1500, "warning", "unifi", "IPS-melding: scan op poort 3306 geblokkeerd"),
        (600, "success", "esxi", "power on → gitlab"),
        (240, "info", "synology", "Hyper Backup → C2 gestart"),
    ]
    for ago_s, lvl, src, msg in reversed(seeded):
        engine.events.appendleft({"time": now - ago_s, "level": lvl, "source": src, "msg": msg})
    engine.events = deque(sorted(engine.events, key=lambda e: -e["time"]), maxlen=200)
    engine.snapshot = engine._build_snapshot()


class ActionIn(BaseModel):
    source: str
    kind: str
    target: str


ALLOWED_ACTIONS = {
    "esxi": {"power_on", "shutdown", "power_off", "reboot"},
    "unifi": {"block", "unblock", "reconnect"},
    "veeam": {"start", "stop"},
}


def _summary(source: str, data: dict) -> str:
    if source == "esxi":
        return f"{len(data.get('hosts', []))} host(s), {len(data.get('vms', []))} VM's, {len(data.get('datastores', []))} datastores"
    if source == "synology":
        return f"{data.get('model')} · {len(data.get('volumes', []))} volume(s), {len(data.get('disks', []))} schijven"
    if source == "unifi":
        return f"{len(data.get('clients', []))} clients, {len(data.get('devices', []))} UniFi-apparaten"
    if source == "veeam":
        return f"{len(data.get('jobs', []))} jobs, {len(data.get('repositories', []))} repositories"
    return "OK"


class SettingsTestIn(BaseModel):
    source: str
    config: dict


def create_app(cfg: Settings | None = None, data_dir: str | None = None) -> FastAPI:
    store = SettingsStore(data_dir)
    if cfg is None:
        cfg = store.load()
    if not cfg.secret_key:
        cfg.secret_key = store.secret()
    engine = Engine(cfg, build_collectors(cfg))

    def S() -> Settings:  # live settings
        return engine.settings

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        mode = "DEMO" if cfg.demo_active else ", ".join(engine.collectors) or "none"
        log.info("LabPilot %s starting – sources: %s – settings in %s", __version__, mode, store.path)
        err = store.check_writable()
        if err:
            log.warning(err)
        await engine.poll()
        if cfg.demo_active:
            seed_demo(engine)
        engine.start()
        yield
        await engine.stop()

    app = FastAPI(title="LabPilot", version=__version__, lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
    app.state.engine = engine

    # -- optional password protection --------------------------------------
    open_paths = ("/login", "/healthz", "/static/", "/favicon.svg")

    @app.middleware("http")
    async def auth_guard(request: Request, call_next):
        if S().password and not request.url.path.startswith(open_paths):
            if not request.session.get("auth"):
                if request.url.path.startswith("/api/"):
                    return JSONResponse({"detail": "Not authenticated"}, status_code=401)
                return RedirectResponse("/login")
        return await call_next(request)

    app.add_middleware(
        SessionMiddleware,
        secret_key=cfg.secret_key,
        session_cookie="labpilot",
        max_age=60 * 60 * 24 * 14,
        same_site="lax",
        https_only=False,
    )

    @app.get("/login", include_in_schema=False)
    async def login_page():
        return FileResponse(STATIC / "login.html")

    @app.post("/login", include_in_schema=False)
    async def login(request: Request):
        form = await request.form()
        pw = S().password
        if pw and hmac.compare_digest(str(form.get("password", "")), pw):
            request.session["auth"] = True
            return RedirectResponse("/", status_code=303)
        await asyncio.sleep(1)
        return RedirectResponse("/login?error=1", status_code=303)

    @app.get("/logout", include_in_schema=False)
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login" if S().password else "/")

    # -- API -----------------------------------------------------------------
    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"status": "ok", "version": __version__}

    @app.get("/api/state")
    async def state():
        return {**engine.snapshot, "version": __version__}

    @app.get("/api/stream")
    async def stream(request: Request):
        async def gen():
            version = -1
            while True:
                if await request.is_disconnected():
                    break
                if version != engine.version:
                    version = engine.version
                    payload = json.dumps({**engine.snapshot, "version": __version__}, default=str)
                    yield f"event: state\ndata: {payload}\n\n"
                else:
                    yield ": keepalive\n\n"
                await engine.wait_for_update(version)

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/refresh")
    async def refresh():
        await engine.poll()
        return {"ok": True}

    # -- settings ------------------------------------------------------------
    @app.get("/api/settings")
    async def get_settings():
        return {
            "schema": SCHEMA,
            "values": SettingsStore.public(S()),
            "placeholder": SECRET_PLACEHOLDER,
            "storage": str(store.path),
            "writable_error": store.check_writable(),
        }

    @app.put("/api/settings")
    async def put_settings(body: dict):
        try:
            new = store.save(body)
        except OSError as exc:
            raise HTTPException(500, f"Opslaan mislukt: {exc.strerror or exc}. Is {store.dir} schrijfbaar?") from exc
        demo_before = S().demo_active
        await engine.reconfigure(new, build_collectors(new))
        if new.demo_active and not demo_before:
            seed_demo(engine)
        return {"ok": True, "values": SettingsStore.public(new), "demo": new.demo_active}

    @app.post("/api/settings/test")
    async def test_settings(body: SettingsTestIn):
        if body.source not in SOURCE_TYPES:
            raise HTTPException(400, "Onbekende bron")
        current = store.raw().get(body.source) or {}
        conf = dict(body.config)
        for k in SECRET_FIELDS:
            if conf.get(k) == SECRET_PLACEHOLDER:
                conf[k] = current.get(k, "")
        probe = build_settings({body.source: {**conf, "active": True}})
        sub = getattr(probe, body.source)
        if not sub.enabled:
            return {"ok": False, "message": "Vul minimaal het adres en de inloggegevens in."}
        probe.demo = False
        collectors = [c for c in build_collectors(probe) if c.name == body.source]
        if not collectors:
            return {"ok": False, "message": "Bron kon niet worden aangemaakt"}
        c = collectors[0]
        try:
            data = await asyncio.wait_for(c.collect(), timeout=25)
            return {"ok": True, "message": f"Verbonden: {_summary(body.source, data)}"}
        except TimeoutError:
            return {"ok": False, "message": "Time-out: geen antwoord binnen 25 seconden"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "message": str(exc) or exc.__class__.__name__}
        finally:
            try:
                await c.close()
            except Exception:  # noqa: BLE001
                pass

    @app.post("/api/actions")
    async def action(body: ActionIn):
        if not (S().actions_enabled or S().demo_active):
            raise HTTPException(403, "Acties staan uit. Zet ze aan via Instellingen › Algemeen.")
        if body.kind not in ALLOWED_ACTIONS.get(body.source, set()):
            raise HTTPException(400, "Onbekende actie")
        collector = engine.collectors.get(body.source)
        if not collector:
            raise HTTPException(404, f"Bron {body.source} is niet geconfigureerd")
        try:
            msg = await collector.action(body.kind, body.target)
        except CollectorError as exc:
            engine.event("critical", body.source, f"Actie mislukt: {exc}")
            raise HTTPException(502, str(exc)) from exc
        engine.event("success", body.source, msg)
        await asyncio.sleep(0.5)
        await engine.poll()
        return {"ok": True, "message": msg}

    # -- frontend ------------------------------------------------------------
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        return FileResponse(STATIC / "favicon.svg", media_type="image/svg+xml")

    @app.get("/", include_in_schema=False)
    async def index():
        html = (STATIC / "index.html").read_text(encoding="utf-8").replace("{{VERSION}}", __version__)
        return HTMLResponse(html)

    return app


app = create_app()
