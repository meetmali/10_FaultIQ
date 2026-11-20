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
    equipment: str = ""
    intensity_unit: str = ""
    definition: Check | None = None  # cited text: same shape as a check
    observed: Check | None = None
    causes: tuple[Check, ...] = ()
    plain_name: str = ""
    component: str = ""
    plain_summary: Check | None = None
    what_to_do: Check | None = None


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

    def cited(item: dict[str, str] | None, name: str) -> Check | None:
        if item is None:
            return None
        if item["source"] not in sources:
            raise LibraryError(f"{name}: cites unknown source {item['source']!r}")
        return Check(text=item["text"], source=item["source"])

    for name, f in raw.get("faults", {}).items():
        checks = tuple(c for c in (cited(x, name) for x in f.get("checks", [])) if c)
        if not checks:
            raise LibraryError(f"{name}: needs at least one check")
        faults[name] = FaultInfo(
            title=f["title"],
            checks=checks,
            equipment=f.get("equipment", ""),
            intensity_unit=f.get("intensity_unit", ""),
            definition=cited(f.get("definition"), name),
            observed=cited(f.get("observed"), name),
            causes=tuple(c for c in (cited(x, name) for x in f.get("causes", [])) if c),
            plain_name=f.get("plain_name", f["title"]),
            component=f.get("component", ""),
            plain_summary=cited(f.get("plain_summary"), name),
            what_to_do=cited(f.get("what_to_do"), name),
        )
    return FaultLibrary(raw.get("review_status", "unreviewed"), sources, faults)


@cache
def fault_library() -> FaultLibrary:
    text = resources.files("faultiq.explain").joinpath("fault_library.toml").read_text()
    return parse_library(text)
