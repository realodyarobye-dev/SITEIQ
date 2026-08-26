"""Comparison mode.

Runs a full analysis on each address, ranks them, and then does the thing the
operator actually wants: names one location and explains why it wins.
"""
import logging

from ..core import db
from .analyze import analyse

log = logging.getLogger("siteiq.compare")

MAX_ADDRESSES = 20


def run(addresses, concept, inputs=None, progress=None):
    addresses = [a.strip() for a in addresses if a.strip()][:MAX_ADDRESSES]
    p = progress or (lambda pct, step: None)
    rows, failures, report_ids = [], [], []

    for i, address in enumerate(addresses):
        base = 5 + (i / max(1, len(addresses))) * 88
        p(base, f"Analysing {i + 1} of {len(addresses)}: {address[:48]}")
        try:
            report = analyse(address, concept, inputs,
                             progress=lambda pct, step, b=base, n=len(addresses):
                             p(b + (pct / 100) * (88 / max(1, n)), step))
        except Exception as exc:  # noqa: BLE001
            log.error("compare failed for %s: %s", address, exc)
            report = None
        if not report:
            failures.append(address)
            continue
        rid = db.save_report(report)
        report_ids.append(rid)
        rows.append(_row(report, rid))

    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    p(96, "Ranking locations")
    winner = _winner(rows)

    return {
        "concept": concept,
        "concept_label": rows[0]["concept_label"] if rows else concept,
        "rows": rows,
        "failures": failures,
        "report_ids": report_ids,
        "winner": winner,
        "count": len(rows),
    }


def _row(report, rid):
    pnl = report["pnl"]["by_scenario"]
    return {
        "report_id": rid,
        "address": report["address"],
        "resolved": report["resolved_address"],
        "concept": report["concept"],
        "concept_label": report["concept_label"],
        "score": report["score"],
        "confidence": report["confidence"]["score"],
        "verdict": report["verdict"],
        "realistic_daily": report["sales"]["scenarios"]["Realistic"]["daily"],
        "strong_daily": report["sales"]["scenarios"]["Strong Operator"]["daily"],
        "conservative_daily": report["sales"]["scenarios"]["Conservative"]["daily"],
        "monthly_profit": pnl["Realistic"]["profit"],
        "conservative_profit": pnl["Conservative"]["profit"],
        "rent": report["rent"]["monthly_rent"],
        "rent_estimated": report["rent"]["estimated"],
        "rent_pct": report["rent_assessment"]["rent_pct"],
        "rent_band": report["rent_assessment"]["band"],
        "competitors": report["competition"]["total"],
        "direct_competitors": report["competition"]["direct_count"],
        "saturation": report["competition"]["saturation_label"],
        "strongest_competitor": (report["competition"]["strongest"] or {}).get("name"),
        "demand": round(next((c["score"] for c in report["score_components"]
                              if c["key"] == "demand"), 0)),
        "opportunity": (report["opportunities"]["best"] or {}).get("title", "None identified"),
        "risk": (report["risks"]["worst"] or {}).get("title", "None identified"),
        "risk_severity": (report["risks"]["worst"] or {}).get("severity", "LOW"),
        "critical_flags": len(report["risks"]["critical"]),
        "lat": report["lat"], "lon": report["lon"],
    }


def _winner(rows):
    if not rows:
        return None
    clean = [r for r in rows if r["critical_flags"] == 0] or rows
    best = clean[0]
    runner = clean[1] if len(clean) > 1 else None

    reasons = []
    if runner:
        if best["score"] - runner["score"] >= 8:
            reasons.append(f"It scores {best['score']} against {runner['score']} for the next best "
                           f"option, which is a clear gap rather than a rounding difference")
        else:
            reasons.append(f"It edges out {runner['address']} by {best['score'] - runner['score']:.1f} "
                           "points, which is close enough that field work could change the answer")
        if best["monthly_profit"] > runner["monthly_profit"]:
            diff = best["monthly_profit"] - runner["monthly_profit"]
            reasons.append(f"it models to ${diff:,}/month more operating profit than the runner-up, "
                           f"about ${diff * 12:,} a year")
    if best["rent_band"] in ("EXCELLENT", "HEALTHY"):
        reasons.append(f"rent sits at {best['rent_pct']}% of modeled sales, inside the healthy range")
    if best["conservative_profit"] > 0:
        reasons.append(f"it still makes about ${best['conservative_profit']:,}/month in the "
                       "conservative case, so the deal does not require everything to go right")
    if best["critical_flags"] == 0:
        reasons.append("it carries no critical red flags")
    reasons.append(f"the main thing to verify is {best['risk'].lower()}")

    return {
        "row": best,
        "headline": f"If you could choose only ONE location, take {best['address']}.",
        "why": ". ".join(r[0].upper() + r[1:] for r in reasons) + ".",
        "caveat": ("This ranking is built entirely on modeled data. Walk the top two locations "
                   "before you commit - a single afternoon on both corners will tell you more "
                   "than any model."),
    }
