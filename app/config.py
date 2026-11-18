"""Configuration loaded from environment variables (12-factor style)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class ESXiConfig:
    host: str = os.getenv("ESXI_HOST", "")
    user: str = os.getenv("ESXI_USER", "")
    password: str = os.getenv("ESXI_PASSWORD", "")
    port: int = _int("ESXI_PORT", 443)
    verify_ssl: bool = _bool("ESXI_VERIFY_SSL", False)

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.user)


@dataclass(frozen=True)
class SynologyConfig:
    url: str = os.getenv("SYNOLOGY_URL", "").rstrip("/")
    user: str = os.getenv("SYNOLOGY_USER", "")
    password: str = os.getenv("SYNOLOGY_PASSWORD", "")
    verify_ssl: bool = _bool("SYNOLOGY_VERIFY_SSL", False)

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.user)


@dataclass(frozen=True)
class UniFiConfig:
    url: str = os.getenv("UNIFI_URL", "").rstrip("/")
    api_key: str = os.getenv("UNIFI_API_KEY", "")
    user: str = os.getenv("UNIFI_USER", "")
    password: str = os.getenv("UNIFI_PASSWORD", "")
    site: str = os.getenv("UNIFI_SITE", "default")
    verify_ssl: bool = _bool("UNIFI_VERIFY_SSL", False)

    @property
    def enabled(self) -> bool:
        return bool(self.url and (self.api_key or self.user))


@dataclass(frozen=True)
class VeeamConfig:
    url: str = os.getenv("VEEAM_URL", "").rstrip("/")
    user: str = os.getenv("VEEAM_USER", "")
    password: str = os.getenv("VEEAM_PASSWORD", "")
    api_version: str = os.getenv("VEEAM_API_VERSION", "1.1-rev2")
    verify_ssl: bool = _bool("VEEAM_VERIFY_SSL", False)

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.user)


@dataclass(frozen=True)
class Settings:
    title: str = os.getenv("LABPILOT_TITLE", "LabPilot")
    poll_interval: int = max(5, _int("POLL_INTERVAL", 15))
    history_points: int = _int("HISTORY_POINTS", 120)
    actions_enabled: bool = _bool("ACTIONS_ENABLED", False)
    password: str = os.getenv("LABPILOT_PASSWORD", "")
    secret_key: str = os.getenv("LABPILOT_SECRET", "")
    snapshot_max_age_days: int = _int("SNAPSHOT_MAX_AGE_DAYS", 14)
    low_space_pct: int = _int("LOW_SPACE_PCT", 15)
    demo: bool = _bool("DEMO_MODE", False)
    esxi: ESXiConfig = field(default_factory=ESXiConfig)
    synology: SynologyConfig = field(default_factory=SynologyConfig)
    unifi: UniFiConfig = field(default_factory=UniFiConfig)
    veeam: VeeamConfig = field(default_factory=VeeamConfig)

    @property
    def any_configured(self) -> bool:
        return any(c.enabled for c in (self.esxi, self.synology, self.unifi, self.veeam))

    @property
    def demo_active(self) -> bool:
        """Demo mode is on when explicitly asked, or when nothing is configured."""
        return self.demo or not self.any_configured


settings = Settings()
