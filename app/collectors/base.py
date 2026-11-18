from __future__ import annotations

import time
from typing import Any


class CollectorError(Exception):
    pass


class Collector:
    """Base class: every source returns a normalised dict from collect()."""

    name: str = "base"
    label: str = "Base"

    async def collect(self) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    async def action(self, kind: str, target: str, **kwargs: Any) -> str:
        raise CollectorError(f"Action '{kind}' is not supported by {self.label}")

    async def close(self) -> None:
        return None


def now() -> float:
    return time.time()
