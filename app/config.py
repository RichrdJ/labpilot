"""Configuration.

Settings are edited in the web UI and stored as JSON in DATA_DIR (a Docker volume).
Environment variables are still honoured as initial defaults, so existing setups keep working.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any

log = logging.getLogger("labpilot.config")

SECRET_PLACEHOLDER = "__unchanged__"


def _bool(val: Any, default: bool = False) -> bool:
    if val is None or val == "":
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _int(val: Any, default: int) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


@dataclass
class ESXiConfig:
    active: bool = True
    host: str = ""
    port: int = 443
    user: str = ""
    password: str = ""
    verify_ssl: bool = False

    @property
    def enabled(self) -> bool:
        return bool(self.active and self.host and self.user)


@dataclass
class SynologyConfig:
    active: bool = True
    url: str = ""
    user: str = ""
    password: str = ""
    verify_ssl: bool = False

    @property
    def enabled(self) -> bool:
        return bool(self.active and self.url and self.user)


@dataclass
class UniFiConfig:
    active: bool = True
    url: str = ""
    user: str = ""
    password: str = ""
    api_key: str = ""
    site: str = "default"
    verify_ssl: bool = False

    @property
    def enabled(self) -> bool:
        return bool(self.active and self.url and (self.api_key or self.user))


@dataclass
class VeeamConfig:
    active: bool = True
    url: str = ""
    user: str = ""
    password: str = ""
    api_version: str = "1.1-rev2"
    verify_ssl: bool = False

    @property
    def enabled(self) -> bool:
        return bool(self.active and self.url and self.user)


SOURCE_TYPES = {"esxi": ESXiConfig, "synology": SynologyConfig, "unifi": UniFiConfig, "veeam": VeeamConfig}
SECRET_FIELDS = {"password", "api_key"}

# Field metadata for the settings UI: (name, label, type, placeholder/help)
SCHEMA: dict[str, dict[str, Any]] = {
    "general": {
        "label": "Algemeen",
        "fields": [
            ("title", "Naam van het dashboard", "text", "LabPilot"),
            ("poll_interval", "Ververs-interval (seconden)", "number", "15"),
            ("actions_enabled", "Acties toestaan (VM aan/uit, blokkeren, jobs starten)", "bool", ""),
            ("password", "Inlogwachtwoord voor het dashboard", "password", "Leeg = geen login"),
            ("snapshot_max_age_days", "Snapshot is oud na (dagen)", "number", "14"),
            ("low_space_pct", "Waarschuwen bij minder dan (% vrij)", "number", "15"),
            ("demo", "Demomodus forceren", "bool", ""),
        ],
    },
    "esxi": {
        "label": "VMware ESXi / vCenter",
        "fields": [
            ("host", "Host of IP-adres", "text", "192.168.1.10"),
            ("port", "Poort", "number", "443"),
            ("user", "Gebruiker", "text", "labpilot"),
            ("password", "Wachtwoord", "password", ""),
            ("verify_ssl", "SSL-certificaat controleren", "bool", ""),
        ],
    },
    "synology": {
        "label": "Synology DSM",
        "fields": [
            ("url", "URL", "text", "https://192.168.1.20:5001"),
            ("user", "Gebruiker", "text", "labpilot"),
            ("password", "Wachtwoord", "password", ""),
            ("verify_ssl", "SSL-certificaat controleren", "bool", ""),
        ],
    },
    "unifi": {
        "label": "UniFi (UDM / UDM Pro)",
        "fields": [
            ("url", "URL", "text", "https://192.168.1.1"),
            ("user", "Lokale gebruiker", "text", "labpilot"),
            ("password", "Wachtwoord", "password", ""),
            ("api_key", "Of: API-key", "password", "Optioneel, in plaats van gebruiker"),
            ("site", "Site", "text", "default"),
            ("verify_ssl", "SSL-certificaat controleren", "bool", ""),
        ],
    },
    "veeam": {
        "label": "Veeam Backup & Replication",
        "fields": [
            ("url", "URL (REST API)", "text", "https://192.168.1.30:9419"),
            ("user", "Gebruiker", "text", "DOMEIN\\labpilot"),
            ("password", "Wachtwoord", "password", ""),
            ("api_version", "API-versie", "text", "1.1-rev2"),
            ("verify_ssl", "SSL-certificaat controleren", "bool", ""),
        ],
    },
}


@dataclass
class Settings:
    title: str = "LabPilot"
    poll_interval: int = 15
    history_points: int = 120
    actions_enabled: bool = False
    password: str = ""
    secret_key: str = ""
    snapshot_max_age_days: int = 14
    low_space_pct: int = 15
    demo: bool = False
    esxi: ESXiConfig = field(default_factory=ESXiConfig)
    synology: SynologyConfig = field(default_factory=SynologyConfig)
    unifi: UniFiConfig = field(default_factory=UniFiConfig)
    veeam: VeeamConfig = field(default_factory=VeeamConfig)

    def __post_init__(self) -> None:
        self.poll_interval = max(5, _int(self.poll_interval, 15))

    @property
    def any_configured(self) -> bool:
        return any(c.enabled for c in (self.esxi, self.synology, self.unifi, self.veeam))

    @property
    def demo_active(self) -> bool:
        """Demo mode is on when explicitly asked, or when nothing is configured."""
        return self.demo or not self.any_configured


GENERAL_KEYS = ("title", "poll_interval", "actions_enabled", "password", "snapshot_max_age_days", "low_space_pct", "demo")


def _coerce(dc_type, data: dict[str, Any]):
    defaults = dc_type()
    kwargs = {}
    for f in fields(dc_type):
        if f.name not in data:
            continue
        cur = getattr(defaults, f.name)
        val = data[f.name]
        if isinstance(cur, bool):
            kwargs[f.name] = _bool(val, cur)
        elif isinstance(cur, int):
            kwargs[f.name] = _int(val, cur)
        else:
            kwargs[f.name] = "" if val is None else str(val).strip()
    return replace(defaults, **kwargs)


def settings_from_env(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Read legacy environment variables into the stored-settings shape."""
    env = dict(os.environ if env is None else env)
    g = lambda k: env.get(k)  # noqa: E731
    out: dict[str, Any] = {
        "title": g("LABPILOT_TITLE"),
        "poll_interval": g("POLL_INTERVAL"),
        "actions_enabled": g("ACTIONS_ENABLED"),
        "password": g("LABPILOT_PASSWORD"),
        "snapshot_max_age_days": g("SNAPSHOT_MAX_AGE_DAYS"),
        "low_space_pct": g("LOW_SPACE_PCT"),
        "demo": g("DEMO_MODE"),
        "esxi": {"host": g("ESXI_HOST"), "port": g("ESXI_PORT"), "user": g("ESXI_USER"),
                 "password": g("ESXI_PASSWORD"), "verify_ssl": g("ESXI_VERIFY_SSL")},
        "synology": {"url": g("SYNOLOGY_URL"), "user": g("SYNOLOGY_USER"),
                     "password": g("SYNOLOGY_PASSWORD"), "verify_ssl": g("SYNOLOGY_VERIFY_SSL")},
        "unifi": {"url": g("UNIFI_URL"), "user": g("UNIFI_USER"), "password": g("UNIFI_PASSWORD"),
                  "api_key": g("UNIFI_API_KEY"), "site": g("UNIFI_SITE"), "verify_ssl": g("UNIFI_VERIFY_SSL")},
        "veeam": {"url": g("VEEAM_URL"), "user": g("VEEAM_USER"), "password": g("VEEAM_PASSWORD"),
                  "api_version": g("VEEAM_API_VERSION"), "verify_ssl": g("VEEAM_VERIFY_SSL")},
    }

    def clean(d: dict[str, Any]) -> dict[str, Any]:
        return {k: (clean(v) if isinstance(v, dict) else v) for k, v in d.items() if v not in (None, "") and v != {}}

    return clean(out)


def build_settings(data: dict[str, Any], secret_key: str = "") -> Settings:
    general = {k: data[k] for k in GENERAL_KEYS if k in data}
    s = _coerce(Settings, general)
    s.secret_key = secret_key
    for name, typ in SOURCE_TYPES.items():
        setattr(s, name, _coerce(typ, data.get(name) or {}))
    return s


class SettingsStore:
    """Persists GUI settings to DATA_DIR/settings.json (and a session secret)."""

    def __init__(self, data_dir: str | os.PathLike | None = None) -> None:
        self.dir = Path(data_dir or os.getenv("DATA_DIR", "/data"))
        self.path = self.dir / "settings.json"
        self.writable_error: str | None = None

    def _read(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            log.error("Kan %s niet lezen: %s", self.path, exc)
            return None

    def secret(self) -> str:
        p = self.dir / ".secret"
        try:
            return p.read_text().strip()
        except OSError:
            key = secrets.token_hex(32)
            try:
                self.dir.mkdir(parents=True, exist_ok=True)
                p.write_text(key)
                os.chmod(p, 0o600)
            except OSError:
                pass
            return key

    def load(self) -> Settings:
        stored = self._read()
        data = stored if stored is not None else settings_from_env()
        return build_settings(data, self.secret())

    def raw(self) -> dict[str, Any]:
        stored = self._read()
        return stored if stored is not None else settings_from_env()

    def save(self, data: dict[str, Any]) -> Settings:
        """Merge incoming data (secrets may be SECRET_PLACEHOLDER = keep) and persist."""
        current = self.raw()
        merged: dict[str, Any] = {}
        for k in GENERAL_KEYS:
            v = data.get(k, current.get(k))
            if k in SECRET_FIELDS and v == SECRET_PLACEHOLDER:
                v = current.get(k, "")
            merged[k] = v
        for name in SOURCE_TYPES:
            cur = current.get(name) or {}
            inc = data.get(name) or {}
            src = {}
            for f in fields(SOURCE_TYPES[name]):
                v = inc.get(f.name, cur.get(f.name))
                if f.name in SECRET_FIELDS and v == SECRET_PLACEHOLDER:
                    v = cur.get(f.name, "")
                if v is not None:
                    src[f.name] = v
            merged[name] = src
        settings = build_settings(merged, self.secret())
        # store normalised values
        out = {k: getattr(settings, k) for k in GENERAL_KEYS}
        for name in SOURCE_TYPES:
            out[name] = asdict(getattr(settings, name))
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)
        return settings

    @staticmethod
    def public(settings: Settings) -> dict[str, Any]:
        """Settings for the UI: secrets are replaced by a placeholder when set."""

        def mask(d: dict[str, Any]) -> dict[str, Any]:
            return {k: (SECRET_PLACEHOLDER if k in SECRET_FIELDS and v else v) for k, v in d.items()}

        out = mask({k: getattr(settings, k) for k in GENERAL_KEYS})
        for name in SOURCE_TYPES:
            cfg = getattr(settings, name)
            out[name] = {**mask(asdict(cfg)), "configured": cfg.enabled}
        return out

    def check_writable(self) -> str | None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            probe = self.dir / ".write-test"
            probe.write_text("ok")
            probe.unlink()
            return None
        except OSError as exc:
            return f"Map {self.dir} is niet schrijfbaar ({exc.strerror or exc})"
