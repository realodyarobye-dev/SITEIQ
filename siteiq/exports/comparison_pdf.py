"""Comparison PDF: the ranked table plus the single recommendation."""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .pdf import LINE, S, VERDICT_COLOUR, _banner, _esc, _table


def build(comparison):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=40, rightMargin=40,
                            topMargin=44, bottomMargin=40,
                            title="SiteIQ Location Comparison", author="SiteIQ")
    story = []
    story.append(Paragraph("SiteIQ location comparison", S["H1"]))
    story.append(Paragraph(
        _esc(f"{comparison['count']} locations - {comparison.get('concept_label', '')} - "
             f"{datetime.now().strftime('%d %B %Y')}"), S["Small"]))
    story.append(Spacer(1, 8))

    if comparison.get("winner"):
        w = comparison["winner"]
        story.append(_banner(w["headline"], colors.HexColor("#0f8a5f")))
        story.append(Paragraph(_esc(w["why"]), S["Body"]))
        story.append(Paragraph(_esc(w["caveat"]), S["Small"]))
        story.append(Spacer(1, 8))

    rows = [["#", "Address", "Score", "Conf", "Realistic\n$/day", "Strong\n$/day",
             "Profit\n$/mo", "Rent", "Rent %", "Comp", "Demand", "Verdict"]]
    for r in comparison["rows"]:
        rows.append([
            str(r["rank"]), r["address"][:40], str(r["score"]), str(r["confidence"]),
            f"${r['realistic_daily']:,}", f"${r['strong_daily']:,}", f"${r['monthly_profit']:,}",
            f"${r['rent']:,}" + ("*" if r["rent_estimated"] else ""), f"{r['rent_pct']}%",
            f"{r['direct_competitors']}/{r['competitors']}", str(r["demand"]), r["verdict"],
        ])
    t = _table(rows, [20, 178, 36, 34, 58, 58, 62, 58, 40, 44, 46, 62], highlight_row=1)
    story.append(t)
    story.append(Paragraph("* rent is a SiteIQ estimate, not an actual quoted rent. "
                           "Comp column shows direct/total competitors within 0.5 mi.", S["Tiny"]))

    story.append(PageBreak())
    story.append(Paragraph("Opportunity and risk by location", S["H1"]))
    rows = [["#", "Address", "Verdict", "Biggest opportunity", "Biggest risk", "Sev"]]
    for r in comparison["rows"]:
        rows.append([str(r["rank"]), r["address"][:34], r["verdict"], r["opportunity"],
                     r["risk"], r["risk_severity"]])
    story.append(_table(rows, [20, 150, 62, 210, 210, 48]))

    if comparison.get("failures"):
        story.append(Spacer(1, 10))
        story.append(Paragraph("Addresses that could not be analysed", S["H2"]))
        for f in comparison["failures"]:
            story.append(Paragraph(_esc(f"- {f} (address could not be located)"), S["Small"]))

    doc.build(story)
    buf.seek(0)
    return buf.read()
