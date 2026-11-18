import os

os.environ.setdefault("DEMO_MODE", "true")

from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


def client(**overrides) -> TestClient:
    cfg = Settings(demo=True, **overrides)
    return TestClient(create_app(cfg))


def test_health():
    with client() as c:
        r = c.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_state_has_all_sources():
    with client() as c:
        s = c.get("/api/state").json()
        for key in ("esxi", "synology", "unifi", "veeam"):
            assert s[key], key
        assert s["meta"]["demo"] is True
        assert s["insights"], "demo should produce insights"
        assert any(c["seen"] for c in s["correlation"]), "VM <-> client MAC correlation"
        assert len(s["history"]["wan_rx"]) > 10


def test_block_and_unblock_client():
    with client() as c:
        mac = "3c:6a:9d:00:91:01"
        assert c.post("/api/actions", json={"source": "unifi", "kind": "block", "target": mac}).status_code == 200
        clients = c.get("/api/state").json()["unifi"]["clients"]
        assert next(x for x in clients if x["mac"] == mac)["blocked"] is True
        assert c.post("/api/actions", json={"source": "unifi", "kind": "unblock", "target": mac}).status_code == 200


def test_vm_power_cycle():
    with client() as c:
        vm = next(v for v in c.get("/api/state").json()["esxi"]["vms"] if v["state"] == "off")
        r = c.post("/api/actions", json={"source": "esxi", "kind": "power_on", "target": vm["id"]})
        assert r.status_code == 200
        vms = {v["id"]: v for v in c.get("/api/state").json()["esxi"]["vms"]}
        assert vms[vm["id"]]["state"] == "on"


def test_unknown_action_rejected():
    with client() as c:
        r = c.post("/api/actions", json={"source": "esxi", "kind": "destroy", "target": "x"})
        assert r.status_code == 400


def test_password_protection():
    with client(password="s3cret", secret_key="test") as c:
        assert c.get("/api/state").status_code == 401
        r = c.get("/", follow_redirects=False)
        assert r.status_code in (302, 307)
        c.post("/login", data={"password": "s3cret"})
        assert c.get("/api/state").status_code == 200


def test_index_served():
    with client() as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "LabPilot" in r.text
