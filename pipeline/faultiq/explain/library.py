"""Loads the fault library: titles, recommended checks and their sources (ADR 0023)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import cache
from importlib import resources

from faultiq.explain.schema import Check, Source


class LibraryError(ValueError):
    """The fault library is malformed (for example, a check cites an unknown source)."""


@dataclass(frozen=True)
class FaultInfo:
    title: str
    checks: tuple[Check, ...]


@dataclass(frozen=True)
class FaultLibrary:
    review_status: str
    sources: dict[str, Source]
    faults: dict[str, FaultInfo]

    def title(self, fault: str) -> str:
        return self.faults[fault].title if fault in self.faults else fault.replace("_", " ")


def parse_library(text: str) -> FaultLibrary:
    raw = tomllib.loads(text)
    sources = {
        sid: Source(id=sid, citation=s["citation"], url=s.get("url"))
        for sid, s in raw.get("sources", {}).items()
    }
    faults = {}
    for name, f in raw.get("faults", {}).items():
        checks = tuple(Check(text=c["text"], source=c["source"]) for c in f.get("checks", []))
        if not checks:
            raise LibraryError(f"{name}: needs at least one check")
        for c in checks:
            if c.source not in sources:
                raise LibraryError(f"{name}: check cites unknown source {c.source!r}")
        faults[name] = FaultInfo(title=f["title"], checks=checks)
    return FaultLibrary(raw.get("review_status", "unreviewed"), sources, faults)


@cache
def fault_library() -> FaultLibrary:
    text = resources.files("faultiq.explain").joinpath("fault_library.toml").read_text()
    return parse_library(text)
