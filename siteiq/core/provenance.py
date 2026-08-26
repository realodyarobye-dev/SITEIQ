"""Data provenance and confidence.

Everything SiteIQ asserts is wrapped in a Fact so the report can always answer
"where did this come from and how much should I trust it?".

Confidence tiers, strongest to weakest:

  OBSERVED    - a third party physically recorded it (a Google listing, a city
                inspection that happened on a date, an OSM survey).
  VERIFIED    - an authoritative published dataset (Census ACS, NYC Open Data).
  USER        - the operator typed it in. Treated as true for their deal.
  MODELED     - SiteIQ computed it from a documented formula. An estimate.
  INFERRED    - reasoned from indirect signals. Weaker than modeled.
  UNAVAILABLE - we do not know. Never silently becomes zero.
"""
from dataclasses import dataclass, field
from typing import Any, Optional

OBSERVED = "OBSERVED"
VERIFIED = "VERIFIED"
USER = "USER-ENTERED"
MODELED = "MODELED"
INFERRED = "INFERRED"
UNAVAILABLE = "UNAVAILABLE"

WEIGHT = {
    OBSERVED: 1.0,
    VERIFIED: 1.0,
    USER: 0.95,
    MODELED: 0.55,
    INFERRED: 0.35,
    UNAVAILABLE: 0.0,
}

# How an evidence tier maps onto the plain-English labels the operator sees.
EVIDENCE_LABEL = {
    OBSERVED: "Confirmed fact",
    VERIFIED: "Confirmed fact",
    USER: "You entered this",
    MODELED: "Estimate",
    INFERRED: "Inference",
    UNAVAILABLE: "Unknown",
}


@dataclass
class Fact:
    """A single value plus the story of where it came from."""
    value: Any = None
    confidence: str = UNAVAILABLE
    source: str = ""
    note: str = ""

    @property
    def known(self) -> bool:
        return self.value is not None and self.confidence != UNAVAILABLE

    @property
    def label(self) -> str:
        return EVIDENCE_LABEL.get(self.confidence, "Unknown")

    def or_else(self, fallback):
        """Value if known, else the fallback. Never turns missing into zero
        implicitly - the caller has to name the fallback."""
        return self.value if self.known else fallback

    def to_dict(self):
        return {
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
            "note": self.note,
            "label": self.label,
            "known": self.known,
        }


def fact(value, confidence, source, note=""):
    if value is None:
        return Fact(None, UNAVAILABLE, source, note or "No data returned by source.")
    return Fact(value, confidence, source, note)


def unknown(source="", note="Data unavailable from connected sources."):
    return Fact(None, UNAVAILABLE, source, note)


@dataclass
class ConfidenceLedger:
    """Tracks the evidence tier of every major conclusion in a report and
    rolls it up into a single 0-100 Data Confidence score."""
    entries: list = field(default_factory=list)

    def add(self, topic: str, confidence: str, source: str, weight: float = 1.0, note: str = ""):
        self.entries.append({
            "topic": topic,
            "confidence": confidence,
            "source": source or "-",
            "weight": weight,
            "note": note,
            "label": EVIDENCE_LABEL.get(confidence, "Unknown"),
        })

    def score(self) -> int:
        if not self.entries:
            return 0
        total = sum(e["weight"] for e in self.entries)
        got = sum(WEIGHT.get(e["confidence"], 0.0) * e["weight"] for e in self.entries)
        return int(round(100 * got / total)) if total else 0

    def missing(self):
        return [e for e in self.entries if e["confidence"] == UNAVAILABLE]

    def to_dict(self):
        return {
            "score": self.score(),
            "entries": self.entries,
            "missing_count": len(self.missing()),
        }


class SourceRegistry:
    """Collects every data source actually touched during an analysis so the
    report can print an honest bibliography."""

    def __init__(self):
        self._sources = {}

    def note(self, name, detail="", url="", used_for=""):
        entry = self._sources.setdefault(name, {"name": name, "detail": detail, "url": url, "used_for": set()})
        if used_for:
            entry["used_for"].add(used_for)
        if detail and not entry["detail"]:
            entry["detail"] = detail
        if url and not entry["url"]:
            entry["url"] = url

    def to_list(self):
        out = []
        for entry in self._sources.values():
            out.append({
                "name": entry["name"],
                "detail": entry["detail"],
                "url": entry["url"],
                "used_for": sorted(entry["used_for"]),
            })
        return sorted(out, key=lambda x: x["name"])
