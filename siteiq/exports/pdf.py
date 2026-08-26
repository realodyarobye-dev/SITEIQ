"""PDF report.

A designed consulting document, not a browser printout: cover page, running
headers and footers, a colour system tied to the verdict, tables with real
styling, and 15-30 pages of content when the data supports it.
"""
import io
import logging
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, Image, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

log = logging.getLogger("siteiq.pdf")

INK = colors.HexColor("#10161f")
MUTED = colors.HexColor("#5d6b7d")
LINE = colors.HexColor("#d8dee7")
PANEL = colors.HexColor("#f4f6f9")
ACCENT = colors.HexColor("#0f6b52")

VERDICT_COLOUR = {
    "TAKE IT": colors.HexColor("#0f8a5f"),
    "STRONG": colors.HexColor("#3f9a4a"),
    "NEGOTIATE": colors.HexColor("#c98617"),
    "MAYBE": colors.HexColor("#c26b1e"),
    "PASS": colors.HexColor("#b53a3a"),
}
SEVERITY_COLOUR = {
    "CRITICAL": colors.HexColor("#b53a3a"),
    "HIGH": colors.HexColor("#d1621f"),
    "MEDIUM": colors.HexColor("#c99617"),
    "LOW": colors.HexColor("#6b7a8d"),
}
THREAT_COLOUR = {
    "VERY HIGH": colors.HexColor("#b53a3a"),
    "HIGH": colors.HexColor("#d1621f"),
    "MEDIUM": colors.HexColor("#c99617"),
    "LOW": colors.HexColor("#4c8a5f"),
}


def _styles():
    s = getSampleStyleSheet()
    def add(name, **kw):
        s.add(ParagraphStyle(name=name, **kw))
    add("Cover", fontName="Helvetica-Bold", fontSize=40, leading=44, textColor=colors.white)
    add("CoverSub", fontName="Helvetica", fontSize=13, leading=18, textColor=colors.HexColor("#c8d4e0"))
    add("CoverMeta", fontName="Helvetica", fontSize=9.5, leading=14, textColor=colors.HexColor("#9fb0c2"))
    add("H1", fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=INK, spaceBefore=6, spaceAfter=8)
    add("H2", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=INK, spaceBefore=12, spaceAfter=5)
    add("H3", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=INK, spaceBefore=8, spaceAfter=3)
    add("Body", fontName="Helvetica", fontSize=9.4, leading=13.4, textColor=INK, spaceAfter=5)
    add("Small", fontName="Helvetica", fontSize=8.2, leading=11.4, textColor=MUTED, spaceAfter=4)
    add("Tiny", fontName="Helvetica-Oblique", fontSize=7.4, leading=10, textColor=MUTED)
    add("Bull", fontName="Helvetica", fontSize=9.4, leading=13.4, textColor=INK,
        leftIndent=13, bulletIndent=3, spaceAfter=3)
    add("Cell", fontName="Helvetica", fontSize=8.3, leading=10.8, textColor=INK)
    add("CellBold", fontName="Helvetica-Bold", fontSize=8.3, leading=10.8, textColor=INK)
    add("CellSmall", fontName="Helvetica", fontSize=7.4, leading=9.6, textColor=MUTED)
    add("Verdict", fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=colors.white)
    add("KPI", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=INK)
    add("KPILabel", fontName="Helvetica-Bold", fontSize=6.8, leading=9, textColor=MUTED)
    return s


S = _styles()


def _esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def P(text, style="Body"):
    return Paragraph(_esc(text), S[style])


def build(report, photos=None):
    """Returns PDF bytes. `photos` is an optional dict of raw image bytes."""
    buf = io.BytesIO()
    photos = photos or {}

    doc = BaseDocTemplate(buf, pagesize=letter, leftMargin=48, rightMargin=48,
                          topMargin=54, bottomMargin=48,
                          title=f"SiteIQ Location Report - {report['address']}",
                          author="SiteIQ", subject="Retail location intelligence")

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    cover_frame = Frame(0, 0, letter[0], letter[1], id="cover",
                        leftPadding=54, rightPadding=54, topPadding=0, bottomPadding=0)

    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=[cover_frame], onPage=_cover_bg(report)),
        PageTemplate(id="Body", frames=[frame], onPage=_chrome(report)),
    ])

    story = []
    _cover(story, report)
    story.append(NextPageTemplate("Body"))
    story.append(PageBreak())

    _verdict(story, report)
    _snapshot(story, report)
    _photos(story, report, photos)
    _block(story, report)
    _history(story, report)
    _competition(story, report)
    _competitor_profiles(story, report, photos)
    _generators(story, report)
    _customers(story, report)
    _dayparts(story, report)
    _demographics(story, report)
    _sales(story, report)
    _economics(story, report)
    _opportunities(story, report)
    _risks(story, report)
    _confidence(story, report)
    _sources(story, report)
    _recommendation(story, report)
    _checklist(story, report)

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ------------------------------------------------------------------- chrome
def _cover_bg(report):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#0b1420"))
        canvas.rect(0, 0, letter[0], letter[1], stroke=0, fill=1)
        v = VERDICT_COLOUR.get(report["verdict"], ACCENT)
        canvas.setFillColor(v)
        canvas.rect(0, 0, letter[0], 16, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#16283c"))
        canvas.circle(letter[0] + 40, letter[1] - 40, 190, stroke=0, fill=1)
        canvas.restoreState()
    return draw


def _chrome(report):
    def draw(canvas, doc):
        canvas.saveState()
        w, h = letter
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(48, h - 40, w - 48, h - 40)
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.setFillColor(INK)
        canvas.drawString(48, h - 34, "SITEIQ LOCATION INTELLIGENCE REPORT")
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(w - 48, h - 34, str(report["address"])[:70])
        canvas.line(48, 38, w - 48, 38)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(48, 28, "Estimates are modeled from public data and are not measured "
                                  "sales or foot traffic. Verify before committing capital.")
        canvas.drawRightString(w - 48, 28, f"Page {doc.page - 1}")
        canvas.restoreState()
    return draw


# -------------------------------------------------------------------- pages
def _cover(story, r):
    story.append(Spacer(1, 150))
    story.append(Paragraph("SITE<font color='#5ee0a0'>IQ</font>",
                           ParagraphStyle("brand", fontName="Helvetica-Bold", fontSize=26,
                                          textColor=colors.white)))
    story.append(Spacer(1, 26))
    story.append(Paragraph(_esc(r["address"]), S["Cover"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(_esc(r["resolved_address"]), S["CoverSub"]))
    story.append(Spacer(1, 26))

    v = VERDICT_COLOUR.get(r["verdict"], ACCENT)
    t = Table([[Paragraph(f"<b>{_esc(r['verdict'])}</b>", S["Verdict"]),
                Paragraph(f"<b>{r['score']}</b><br/><font size=8>OVERALL SCORE</font>",
                          ParagraphStyle("sc", fontName="Helvetica-Bold", fontSize=26,
                                         textColor=colors.white, alignment=TA_CENTER)),
                Paragraph(f"<b>{r['confidence']['score']}</b><br/><font size=8>DATA CONFIDENCE</font>",
                          ParagraphStyle("cf", fontName="Helvetica-Bold", fontSize=26,
                                         textColor=colors.white, alignment=TA_CENTER))]],
               colWidths=[230, 130, 140], rowHeights=[74])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), v),
        ("BACKGROUND", (1, 0), (2, 0), colors.HexColor("#16283c")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("BOX", (0, 0), (-1, -1), 0, colors.white),
    ]))
    story.append(t)
    story.append(Spacer(1, 30))
    story.append(Paragraph(_esc(r["five_hundred_k"]["headline"]),
                           ParagraphStyle("k", fontName="Helvetica-Bold", fontSize=14, leading=19,
                                          textColor=colors.HexColor("#5ee0a0"))))
    story.append(Spacer(1, 60))
    meta = (f"{r['concept_label']}  |  Prepared {datetime.now().strftime('%d %B %Y')}  |  "
            f"Report {r.get('id') or 'draft'}")
    story.append(Paragraph(_esc(meta), S["CoverMeta"]))
    story.append(Paragraph(
        "Confidential. Prepared for internal investment decision-making. All sales, profit and "
        "traffic figures are modeled estimates derived from public data sources listed in this "
        "report, not measured results.", S["CoverMeta"]))


def _verdict(story, r):
    story.append(P("Executive verdict", "H1"))
    v = VERDICT_COLOUR.get(r["verdict"], ACCENT)
    story.append(_banner(f"{r['verdict']} - score {r['score']}/100, data confidence "
                         f"{r['confidence']['score']}/100", v))
    story.append(P(r["verdict_reason"]))
    story.append(Spacer(1, 6))

    story.append(P("Would I put $500,000 here?", "H2"))
    story.append(P(r["five_hundred_k"]["headline"], "H3"))
    story.append(P(r["five_hundred_k"]["explanation"]))

    sc = r["sales"]["scenarios"]
    pnl = r["pnl"]["by_scenario"]
    story.append(P("Sales and profit at a glance", "H2"))
    rows = [["Scenario", "Daily", "Monthly", "Annual", "Monthly profit", "Margin"]]
    for name in ("Conservative", "Realistic", "Strong Operator", "Elite Operator"):
        s, p = sc[name], pnl[name]
        rows.append([name, f"${s['daily']:,}", f"${s['monthly']:,}", f"${s['annual']:,}",
                     f"${p['profit']:,}", f"{p['margin_pct']}%"])
    story.append(_table(rows, [110, 68, 82, 92, 92, 55], highlight_row=2))
    story.append(P("ESTIMATE / MODELED. Not measured sales.", "Tiny"))

    ra = r["rent_assessment"]
    story.append(Spacer(1, 8))
    facts = [
        ("Rent", f"${r['rent']['monthly_rent']:,}/mo" +
         (" (ESTIMATED)" if r["rent"]["estimated"] else " (you entered)")),
        ("Rent as % of sales", f"{ra['rent_pct']}% - {ra['band']} (healthy is {ra['healthy_pct']}%)"),
        ("Direct competitors", f"{r['competition']['direct_count']} direct, "
                               f"{r['competition']['total']} total within 0.5 mi"),
        ("Strongest competitor", (r["competition"]["strongest"] or {}).get("name", "None identified")),
        ("Biggest opportunity", (r["opportunities"]["best"] or {}).get("title", "None identified")),
        ("Biggest risk", (r["risks"]["worst"] or {}).get("title", "None identified")),
        ("Break-even sales", f"${r['pnl']['breakeven_daily']:,}/day" if r["pnl"].get("breakeven_daily") else "n/a"),
    ]
    story.append(_kv(facts))


def _snapshot(story, r):
    story.append(P("Location snapshot", "H1"))
    b = r["block"]
    rows = [
        ("Address", r["resolved_address"]),
        ("Business type", r["concept_label"]),
        ("Street", b["streets"].get("on_street") or "Unknown"),
        ("Cross street", b["streets"].get("cross_street") or "Unknown"),
        ("Position", "Corner" if b.get("is_corner") else "Mid-block"),
        ("Retail character", b["retail_continuity"][0]),
        ("Storefronts within ~240 ft", str(b.get("storefront_count", 0))),
        ("Borough", r.get("borough") or "Outside NYC - city datasets unavailable"),
    ]
    story.append(_kv(rows))
    story.append(P(b["retail_continuity"][1]))

    story.append(P("What is around you", "H2"))
    rows = [["Radius", "Mapped places", "Food and grocery", "Top categories"]]
    for x in r["radii"]:
        top = ", ".join(f"{k} ({v})" for k, v in list(x["by_category"].items())[:4])
        rows.append([x["label"], str(x["total"]), str(x["food"]), top or "-"])
    story.append(_table(rows, [92, 78, 88, 230]))
    story.append(P("Counts reflect places mapped in OpenStreetMap. Real-world counts are higher; "
                   "absence from the map is not evidence of absence.", "Tiny"))

    story.append(P("Score breakdown", "H2"))
    rows = [["Component", "Score", "Weight", "Contribution", "Basis"]]
    for c in r["score_components"]:
        rows.append([c["label"], f"{c['score']}/100", f"{c['weight'] * 100:.0f}%",
                     str(c["contribution"]), c["note"]])
    story.append(_table(rows, [128, 46, 44, 60, 210]))


def _photos(story, r, photos):
    sv = photos.get("streetview")
    if not sv:
        return
    story.append(P("Storefront and street imagery", "H1"))
    try:
        img = Image(io.BytesIO(sv), width=460, height=288)
        story.append(img)
    except Exception:  # noqa: BLE001
        return
    meta = r.get("streetview") or {}
    story.append(P(f"Google Street View imagery, captured {meta.get('date', 'date unknown')}. "
                   f"{meta.get('copyright', '')}", "Tiny"))
    story.append(P("Street View imagery may be years old. Confirm the current condition of the "
                   "storefront, signage rights, scaffolding and sightlines in person.", "Small"))


def _block(story, r):
    story.append(PageBreak())
    story.append(P("The block", "H1"))
    b = r["block"]
    story.append(P(b["street_axis_desc"] + " " + b["walk_note"], "Small"))

    for title, items in (("Immediately to one side", b["immediate_left"]),
                         ("Immediately to the other side", b["immediate_right"]),
                         ("Across the street", b["across_street"]),
                         ("On the corner", b["corner_businesses"])):
        if not items:
            continue
        story.append(P(title, "H3"))
        rows = [["Business", "Type", "Distance"]]
        for n in items[:8]:
            rows.append([n["name"], n["category_label"], f"{n['distance_ft']} ft"])
        story.append(_table(rows, [250, 140, 78]))

    story.append(P("Method: the street axis is inferred from the alignment of mapped storefronts "
                   "and road geometry. Left, right and across are computed estimates, not a "
                   "physical survey.", "Tiny"))

    ent = b["entrances"]
    if any(ent.values()):
        story.append(P("Entrances and anchors on the block", "H2"))
        rows = [["Type", "What is there"]]
        for key, label in (("transit", "Transit entrances"), ("residential", "Residential entrances"),
                           ("office", "Office entrances"), ("schools", "Schools")):
            if ent.get(key):
                rows.append([label, ", ".join(f"{x['name']} ({x['distance_ft']} ft)"
                                              for x in ent[key][:4])])
        if len(rows) > 1:
            story.append(_table(rows, [120, 348]))

    vac = b["vacancy"]
    story.append(P("Vacancies", "H3"))
    if vac["detected"]:
        story.append(P(f"{vac['detected']} former storefronts tagged nearby: " +
                       ", ".join(f"{v['name']} ({v['distance_ft']} ft)" for v in vac["items"])))
    else:
        story.append(P("No tagged vacancies detected."))
    story.append(P(vac["note"], "Tiny"))

    if b.get("construction"):
        story.append(P("Construction activity on this street", "H3"))
        rows = [["Address", "Permit type", "Year"]]
        for c in b["construction"][:8]:
            rows.append([c["address"], c["type"], str(c["year"])])
        story.append(_table(rows, [220, 170, 78]))
        story.append(P("Source: NYC Department of Buildings permit issuance records.", "Tiny"))

    bld = b.get("building") or {}
    if bld.get("available"):
        story.append(P("Building and land use on the block", "H2"))
        rows = [
            ("Residential units on surrounding lots", f"{bld['residential_units']:,}"),
            ("Ground-floor retail area", f"{bld['retail_sqft']:,} sq ft"),
            ("Office area", f"{bld['office_sqft']:,} sq ft"),
            ("Median year built", str(bld.get("median_year_built") or "Unknown")),
            ("Average building height", f"{bld.get('avg_floors')} floors" if bld.get("avg_floors") else "Unknown"),
        ]
        story.append(_kv(rows))
        if bld.get("large_residential_buildings"):
            story.append(P("Largest residential buildings nearby", "H3"))
            rows = [["Address", "Units", "Floors"]]
            for x in bld["large_residential_buildings"][:6]:
                rows.append([x["address"], f"{x['units']:,}", str(x["floors"])])
            story.append(_table(rows, [280, 90, 90]))
        story.append(P(f"Source: {bld.get('source')}. Covers tax lots within about "
                       f"{bld.get('radius_mi', 0.05)} mi.", "Tiny"))


def _history(story, r):
    sh = r.get("storefront_history") or {}
    churn = (r["block"].get("churn") or {})
    if not sh.get("available") and not churn.get("available"):
        return
    story.append(P("Business longevity and location history", "H1"))

    if sh.get("available"):
        story.append(P("What has occupied this exact storefront", "H2"))
        rows = [["Business", "Type", "In records", "Status"]]
        for t in sh["tenants"][:14]:
            span = (f"{t['first_year']}" if t["first_year"] == t["last_year"]
                    else f"{t['first_year']}-{t['last_year']}")
            rows.append([t["name"], t["kind"], span,
                         "Appears current" if t["appears_current"] else "No recent records"])
        story.append(_table(rows, [180, 130, 78, 100]))
        story.append(P("CONFIRMED FACT for the years shown - these are dates on which the city "
                       "recorded activity at this address. Absence of recent records is an "
                       "INFERENCE that a business closed, not proof.", "Tiny"))
    else:
        story.append(P("No NYC business or inspection records matched this exact address. That "
                       "may mean the space was never a licensed food business, or that the "
                       "address format does not match city records. UNKNOWN, not empty.", "Small"))

    if churn.get("available"):
        story.append(P("Does this block hold its businesses?", "H2"))
        story.append(_banner(f"{churn['verdict']} - {churn['churn_rate']}% of food businesses on "
                             f"record are no longer active", 
                             colors.HexColor("#b53a3a") if churn["verdict"] == "HIGH TURNOVER"
                             else colors.HexColor("#4c8a5f")))
        story.append(P(churn["note"]))
        rows = [("Food businesses on record nearby", str(churn["total_on_record"])),
                ("Currently active", str(churn["currently_active"])),
                ("No longer appearing in records", str(churn["no_longer_active"])),
                ("Operating 8+ years", str(churn["long_lived"])),
                ("Closed within 2 years of opening", str(churn["short_lived_closures"]))]
        story.append(_kv(rows))
        if churn.get("oldest_neighbours"):
            story.append(P("Longest-surviving neighbours", "H3"))
            rows = [["Business", "Confirmed since at least", "Years in records"]]
            for x in churn["oldest_neighbours"]:
                rows.append([x["name"], str(x["since"]), str(x["years"])])
            story.append(_table(rows, [240, 130, 90]))
        story.append(P(churn["caveat"], "Tiny"))


def _competition(story, r):
    story.append(PageBreak())
    story.append(P("Competition", "H1"))
    c = r["competition"]
    story.append(_banner(f"{c['saturation_label']} - pressure index {c['pressure']}",
                         colors.HexColor("#b53a3a") if c["pressure"] >= 6 else ACCENT))
    rows = [
        ("Total competitors within 0.5 mi", str(c["total"])),
        ("Direct competitors", str(c["direct_count"])),
        ("Within one block", str(c["within_block"])),
        ("Operating 24 hours", str(c["open_24h_count"])),
        ("Average rating", f"{c['avg_rating']}★ across {c['rated_count']} rated" if c["avg_rating"]
         else "No rating data available"),
        ("Weak incumbents (under 3.9★)", str(len(c["weak_incumbents"]))),
    ]
    story.append(_kv(rows))

    if c.get("cross_check"):
        story.append(P(c["cross_check"]["note"], "Small"))

    story.append(P("Competitive landscape", "H2"))
    rows = [["#", "Business", "Type", "Dist", "Rating", "Reviews", "24h", "Threat"]]
    for x in r["competitors"][:22]:
        rows.append([str(x["rank"]), x["name"][:34], x["category_label"],
                     f"{x['distance_mi']:.2f}mi" if x.get("distance_mi") else "-",
                     f"{x['rating']}★" if x.get("rating") else "-",
                     f"{x['reviews']:,}" if x.get("reviews") else "-",
                     "Yes" if x.get("open_24h") else "-", x["threat"]])
    story.append(_table(rows, [18, 148, 82, 42, 40, 48, 28, 62], threat_col=7))


def _competitor_profiles(story, r, photos):
    comps = [c for c in r["competitors"] if c["threat"] in ("VERY HIGH", "HIGH")][:8]
    if not comps:
        comps = r["competitors"][:5]
    if not comps:
        return
    story.append(PageBreak())
    story.append(P("Competitor profiles", "H1"))
    story.append(P("The operators most likely to take your customers, in order.", "Small"))

    for c in comps:
        block = []
        colour = THREAT_COLOUR.get(c["threat"], MUTED)
        header = Table([[Paragraph(f"<b>{_esc(c['name'])}</b>", S["H3"]),
                         Paragraph(f"<b>{_esc(c['threat'])}</b>",
                                   ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=9,
                                                  textColor=colors.white, alignment=TA_CENTER))]],
                        colWidths=[390, 78])
        header.setStyle(TableStyle([
            ("BACKGROUND", (1, 0), (1, 0), colour),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        block.append(header)

        facts = []
        if c.get("distance_mi") is not None:
            facts.append(f"{c['distance_mi']:.2f} mi ({int(c['distance_mi'] * 5280)} ft, "
                         f"~{c.get('walk_minutes', '?')} min walk)")
        if c.get("rating"):
            facts.append(f"{c['rating']}★ from {c.get('reviews', 0):,} reviews")
        elif c.get("reviews"):
            facts.append(f"{c['reviews']:,} reviews")
        facts.append(c["category_label"])
        if c.get("open_24h"):
            facts.append("Open 24 hours")
        elif c.get("open_now") is not None:
            facts.append("Open now" if c["open_now"] else "Currently closed")
        if c.get("price_level"):
            facts.append(f"Price {c['price_level']}")
        if c.get("since"):
            facts.append(c["since"]["statement"])
        if c.get("phone"):
            facts.append(c["phone"])
        block.append(P(" | ".join(facts), "Small"))

        photo = photos.get(f"comp_{c.get('id') or c['name']}")
        why = Paragraph(_esc(c["why"]), S["Cell"])
        if photo:
            try:
                thumb = Image(io.BytesIO(photo), width=118, height=88)
                t = Table([[thumb, why]], colWidths=[124, 344])
                t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                       ("LEFTPADDING", (0, 0), (0, 0), 0)]))
                block.append(t)
            except Exception:  # noqa: BLE001
                block.append(why)
        else:
            block.append(why)

        threat_rows = [["Prepared food", c["prepared_food_threat"],
                        "Convenience", c["convenience_threat"],
                        "Delivery", c["delivery_threat"]]]
        tt = Table(threat_rows, colWidths=[76, 78, 76, 78, 76, 78])
        tt.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 7.4),
            ("BACKGROUND", (0, 0), (0, 0), PANEL), ("BACKGROUND", (2, 0), (2, 0), PANEL),
            ("BACKGROUND", (4, 0), (4, 0), PANEL),
            ("TEXTCOLOR", (1, 0), (1, 0), THREAT_COLOUR.get(c["prepared_food_threat"], MUTED)),
            ("TEXTCOLOR", (3, 0), (3, 0), THREAT_COLOUR.get(c["convenience_threat"], MUTED)),
            ("TEXTCOLOR", (5, 0), (5, 0), THREAT_COLOUR.get(c["delivery_threat"], MUTED)),
            ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
            ("FONTNAME", (3, 0), (3, 0), "Helvetica-Bold"),
            ("FONTNAME", (5, 0), (5, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        block.append(tt)
        block.append(Spacer(1, 10))
        story.append(KeepTogether(block))


def _generators(story, r):
    story.append(PageBreak())
    story.append(P("Demand generators", "H1"))
    story.append(P("What physically puts people on this sidewalk, ranked by how much this "
                   "specific business can monetise them.", "Small"))
    g = r["generators"]
    rows = [["Generator", "Type", "Distance", "Walk", "Relevance"]]
    for x in g["items"][:22]:
        rows.append([x["name"][:38], x["category_label"], f"{x['distance_ft']} ft",
                     f"{x['walk_minutes']} min", f"{x['relevance']}/100"])
    story.append(_table(rows, [176, 108, 62, 48, 62]))

    story.append(P("Why the top generators matter here", "H2"))
    seen = set()
    for x in g["top"][:6]:
        if x["category"] in seen:
            continue
        seen.add(x["category"])
        story.append(P(f"{x['name']} - {x['category_label']}, {x['distance_ft']} ft", "H3"))
        story.append(P(x["why"]))


def _customers(story, r):
    story.append(P("Customer profile", "H1"))
    c = r["customers"]
    story.append(P(c["method"], "Small"))
    for x in c["ranked"]:
        story.append(P(f"{x['label'].upper()} - {x['tier']} ({x['score']}/100)", "H3"))
        story.append(P(x["buys"]))
        story.append(P(x["value"], "Small"))
    story.append(P(f"Customer mix: {c['concentration']['level']}", "H2"))
    story.append(P(c["concentration"]["note"]))


def _dayparts(story, r):
    story.append(PageBreak())
    story.append(P("Daypart intelligence", "H1"))
    d = r["dayparts"]
    story.append(_banner(f"MODELED - {d['shape'][0]}", colors.HexColor("#c98617")))
    story.append(P(d["disclaimer"], "Small"))

    rows = [["Window", "Weekday", "Weekend", "Blended", "What drives it"]]
    for w in d["windows"]:
        rows.append([w["label"], f"{w['weekday']}/100", f"{w['weekend']}/100",
                     f"{w['score']}/100", ", ".join(w["drivers"]) or "general activity"])
    story.append(_table(rows, [76, 54, 54, 54, 230]))

    story.append(P("Summary periods", "H2"))
    rows = [["Period", "Weekday", "Weekend", "Blended"]]
    for name, v in d["summary"].items():
        rows.append([name, f"{v['weekday']}/100", f"{v['weekend']}/100", f"{v['score']}/100"])
    story.append(_table(rows, [130, 88, 88, 88]))

    story.append(P("Notes by window", "H2"))
    for w in d["windows"]:
        story.append(P(f"{w['label']}: {w['note']}", "Small"))
    story.append(P(f"Peak: {d['peak']['label']}. Weakest: {d['trough']['label']}. {d['shape'][1]}"))


def _demographics(story, r):
    story.append(P("Demographics", "H1"))
    d = r["demographics"]
    if not d.get("available"):
        story.append(P("Census data could not be resolved for this coordinate. UNAVAILABLE - not "
                       "zero. All population-driven estimates in this report are weaker as a result."))
        return
    f = d["facts"]
    story.append(P(f"Census tract {d.get('tract_name')} - {d['source']}", "Small"))
    rows = []
    for key, label, fmt in (("population", "Tract population", "{:,.0f}"),
                            ("households", "Tract households", "{:,.0f}"),
                            ("median_income", "Median household income", "${:,.0f}"),
                            ("median_age", "Median age", "{:.1f}"),
                            ("density_sq_mi", "Population density (per sq mi)", "{:,.0f}"),
                            ("avg_household_size", "Average household size", "{:.2f}"),
                            ("median_rent", "Median residential rent", "${:,.0f}")):
        fv = f.get(key) or {}
        val = fmt.format(fv["value"]) if fv.get("known") else "UNAVAILABLE"
        rows.append((label, f"{val}   [{fv.get('label', 'Unknown')}]"))
    story.append(_kv(rows))

    if d.get("radius_estimates"):
        story.append(P("Estimated residents by radius", "H2"))
        rows = [["Radius", "Estimated residents", "Basis"]]
        for radius, fv in sorted(d["radius_estimates"].items()):
            rows.append([f"{radius} mi",
                         f"{fv['value']:,}" if fv.get("known") else "UNAVAILABLE",
                         "INFERRED from tract density"])
        story.append(_table(rows, [80, 130, 258]))
        story.append(P("These are derived from measured tract density applied to a circle. They "
                       "are INFERENCES, not counts, and they assume even distribution which no "
                       "real block has.", "Tiny"))

    extras = []
    ch = d.get("character") or {}
    if ch.get("value"):
        extras.append(("Residential character", ch["value"]))
    tc = d.get("transit_commute_share") or {}
    if tc.get("known"):
        extras.append(("Transit or walk commuters", f"{tc['value'] * 100:.0f}% of local workers"))
    rs = d.get("renter_share") or {}
    if rs.get("known"):
        extras.append(("Renter-occupied housing", f"{rs['value'] * 100:.0f}%"))
    if d.get("income_mix"):
        m = d["income_mix"]
        extras.append(("Households earning $100k+", f"{m['high_share'] * 100:.0f}%"))
        extras.append(("Households earning under $50k", f"{m['low_share'] * 100:.0f}%"))
    if extras:
        story.append(_kv(extras))


def _sales(story, r):
    story.append(PageBreak())
    story.append(P("Sales potential", "H1"))
    s = r["sales"]
    story.append(_banner("MODELED ESTIMATE - built from customer pools, not measured sales",
                         colors.HexColor("#c98617")))

    rows = [["Scenario", "Daily", "Weekly", "Monthly", "Annual"]]
    for name in ("Conservative", "Realistic", "Strong Operator", "Elite Operator"):
        x = s["scenarios"][name]
        rows.append([name, f"${x['daily']:,}", f"${x['weekly']:,}",
                     f"${x['monthly']:,}", f"${x['annual']:,}"])
    story.append(_table(rows, [122, 78, 88, 90, 90], highlight_row=2))

    for name in ("Conservative", "Realistic", "Strong Operator", "Elite Operator"):
        story.append(P(f"{name}: {s['scenarios'][name]['meaning']}", "Small"))

    story.append(P("How the estimate is built", "H2"))
    story.append(P("Daily transactions are estimated pool by pool: how many people of each type "
                   "pass within capture range, multiplied by the share that transact on a normal "
                   "day, adjusted for how much competition splits them."))
    rows = [["Customer pool", "Estimated pool", "Base capture", "After competition", "Daily transactions"]]
    for line in s["transaction_lines"]:
        rows.append([line["label"], f"{line['pool_size']:,}", f"{line['capture_pct']}%",
                     f"{line['effective_pct']}%", f"{line['transactions']:.0f}"])
    rows.append(["TOTAL before modifiers", "", "", "", f"{s['base_transactions']:.0f}"])
    story.append(_table(rows, [150, 82, 68, 82, 86], bold_last=True))
    story.append(P(s["competitive_note"], "Small"))
    cap = s.get("capacity")
    if cap:
        story.append(P("Physical capacity ceiling", "H3"))
        story.append(P(f"Modeled demand is {cap['raw_demand']} transactions/day against a store "
                       f"capacity of about {cap['max_daily']:,.0f}/day, so the store runs at "
                       f"{cap['utilisation']}% of capacity. {cap['note']}"))
    story.append(P(f"Average ticket assumption: ${s['ticket']:.2f} (MODELED for this concept).", "Small"))

    story.append(P("Location modifiers applied", "H2"))
    rows = [["Modifier", "Effect", "Why"]]
    for m in s["modifiers"]:
        rows.append([m["name"], f"{m['effect_pct']:+.0f}%", m["note"]])
    rows.append(["Combined", f"x{s['total_modifier']}", ""])
    story.append(_table(rows, [110, 52, 306], bold_last=True))

    if s["delivery"].get("applicable"):
        story.append(P("Delivery channel", "H2"))
        story.append(P(s["delivery"]["note"]))

    story.append(P("Biggest factors pushing the estimate UP", "H2"))
    for x in s["drivers_up"]:
        story.append(Paragraph(f"<b>{_esc(x['factor'])}</b> ({_esc(x['effect'])}) - {_esc(x['detail'])}",
                               S["Bull"], bulletText="+"))
    story.append(P("Biggest factors pushing the estimate DOWN", "H2"))
    if s["drivers_down"]:
        for x in s["drivers_down"]:
            story.append(Paragraph(f"<b>{_esc(x['factor'])}</b> ({_esc(x['effect'])}) - {_esc(x['detail'])}",
                                   S["Bull"], bulletText="-"))
    else:
        story.append(P("No material negative modifiers identified."))

    story.append(Spacer(1, 6))
    story.append(P(s["disclaimer"], "Small"))


def _economics(story, r):
    story.append(PageBreak())
    story.append(P("Rent and operating economics", "H1"))
    rent, ra = r["rent"], r["rent_assessment"]
    story.append(_banner(f"Rent {ra['rent_pct']}% of modeled sales - {ra['band']}",
                         colors.HexColor("#b53a3a") if ra["band"] in ("HIGH", "UNSUSTAINABLE")
                         else ACCENT))
    story.append(P(rent["note"]))
    story.append(P(ra["verdict"]))
    rows = [
        ("Monthly rent", f"${rent['monthly_rent']:,}" +
         (" (ESTIMATED)" if rent["estimated"] else " (you entered)")),
        ("Assumed size", f"{rent['sqft']:,} sq ft" + (" (estimated)" if rent["sqft_estimated"] else "")),
        ("Implied annual rate", f"${rent['annual_psf']:,}/sq ft/yr" if rent.get("annual_psf") else "n/a"),
        ("Healthy rent for this concept", f"{ra['healthy_pct']}% of sales"),
        ("Maximum supportable rent", f"${ra['max_supportable_rent']:,}/month"),
    ]
    if ra["gap"] > 0:
        rows.append(("Negotiation target", f"Reduce by about ${ra['gap']:,}/month"))
    story.append(_kv(rows))

    story.append(P("Monthly operating P&L by scenario", "H2"))
    pnl = r["pnl"]
    order = ["Conservative", "Realistic", "Strong Operator", "Elite Operator"]
    rows = [["Line"] + order]
    fields = [("revenue", "Sales", "${:,}"), ("cogs", "Cost of goods", "${:,}"),
              ("labour", "Labour", "${:,}"), ("delivery_commission", "Delivery commission", "${:,}"),
              ("card_fees", "Card processing", "${:,}"), ("rent", "Rent", "${:,}"),
              ("fixed", "Other fixed costs", "${:,}"), ("profit", "OPERATING PROFIT", "${:,}"),
              ("margin_pct", "Margin", "{}%"), ("annual_profit", "Annual profit", "${:,}")]
    for key, label, fmt in fields:
        rows.append([label] + [fmt.format(pnl["by_scenario"][o][key]) for o in order])
    story.append(_table(rows, [124, 86, 86, 86, 86], bold_rows=[8, 11]))

    if pnl.get("breakeven_daily"):
        story.append(P(f"Break-even is about ${pnl['breakeven_daily']:,}/day in sales, covering "
                       f"rent, other fixed costs and the ${pnl['labour_floor']:,}/month it takes "
                       f"to physically staff {pnl['hours_per_week']} hours a week.", "H3"))

    story.append(P("Model assumptions", "H2"))
    for a in pnl["assumptions"]:
        story.append(Paragraph(_esc(a), S["Bull"], bulletText="\u2022"))


def _opportunities(story, r):
    story.append(PageBreak())
    story.append(P("Opportunities", "H1"))
    o = r["opportunities"]
    story.append(P(o["method"], "Small"))
    if not o["items"]:
        story.append(P("No multi-signal opportunities were detected. That is a finding in itself: "
                       "this location does not present an obvious gap to attack. You would be "
                       "competing on execution alone."))
        return
    for x in o["items"]:
        story.append(P(f"{x['title']} [{x['strength']}]", "H3"))
        for sig in x["signals"]:
            story.append(Paragraph(_esc(sig), S["Bull"], bulletText="\u2022"))
        story.append(P(f"What to do: {x['action']}"))
        story.append(Spacer(1, 4))


def _risks(story, r):
    story.append(P("Risks and red flags", "H1"))
    risks = r["risks"]
    counts = " | ".join(f"{k}: {v}" for k, v in risks["counts"].items()) or "None detected"
    story.append(_banner(counts, colors.HexColor("#b53a3a") if risks["has_critical"] else MUTED))
    for x in risks["items"]:
        colour = SEVERITY_COLOUR.get(x["severity"], MUTED)
        head = Table([[Paragraph(f"<b>{_esc(x['title'])}</b>", S["H3"]),
                       Paragraph(f"<b>{_esc(x['severity'])}</b>",
                                 ParagraphStyle("s", fontName="Helvetica-Bold", fontSize=8,
                                                textColor=colors.white, alignment=TA_CENTER))]],
                     colWidths=[390, 78])
        head.setStyle(TableStyle([("BACKGROUND", (1, 0), (1, 0), colour),
                                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                  ("LEFTPADDING", (0, 0), (0, 0), 0),
                                  ("TOPPADDING", (0, 0), (-1, -1), 3),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        parts = [head, P(x["detail"])]
        if x.get("action"):
            parts.append(P(f"What to do: {x['action']}", "Small"))
        parts.append(Spacer(1, 6))
        story.append(KeepTogether(parts))


def _confidence(story, r):
    story.append(PageBreak())
    story.append(P("Data confidence", "H1"))
    c = r["confidence"]
    story.append(_banner(f"DATA CONFIDENCE {c['score']}/100 - {c['missing_count']} inputs unavailable",
                         ACCENT if c["score"] >= 65 else colors.HexColor("#c98617")))
    story.append(P("Every major conclusion in this report is graded by how it was established. "
                   "OBSERVED and VERIFIED mean somebody recorded it. MODELED means SiteIQ "
                   "calculated it. INFERRED means it was reasoned from indirect signals. "
                   "UNAVAILABLE means unknown - it is never silently treated as zero."))
    rows = [["Conclusion", "Evidence", "Source", "Note"]]
    for e in c["entries"]:
        rows.append([e["topic"], e["confidence"], e["source"], e.get("note", "")])
    story.append(_table(rows, [124, 74, 118, 152]))


def _sources(story, r):
    story.append(P("Sources", "H1"))
    rows = [["Source", "What it provided"]]
    for s in r["sources"]:
        rows.append([f"{s['name']}\n{s['detail']}", "; ".join(s["used_for"]) or s["detail"]])
    story.append(_table(rows, [176, 292]))
    story.append(P("SiteIQ uses only public and licensed APIs. It does not scrape services in "
                   "violation of their terms, and it does not fabricate any value it cannot "
                   "source.", "Tiny"))


def _recommendation(story, r):
    story.append(PageBreak())
    story.append(P("Final recommendation", "H1"))
    v = VERDICT_COLOUR.get(r["verdict"], ACCENT)
    story.append(_banner(f"{r['verdict']}", v))
    story.append(P(r["verdict_reason"]))
    story.append(Spacer(1, 8))
    story.append(P(r["five_hundred_k"]["headline"], "H2"))
    story.append(P(r["five_hundred_k"]["explanation"]))
    story.append(Spacer(1, 8))

    if r["opportunities"].get("best"):
        story.append(P("The single biggest reason to do this deal", "H3"))
        story.append(P(r["opportunities"]["best"]["title"]))
        story.append(P(r["opportunities"]["best"]["action"], "Small"))
    if r["risks"].get("worst"):
        story.append(P("The single biggest reason not to", "H3"))
        story.append(P(r["risks"]["worst"]["title"]))
        story.append(P(r["risks"]["worst"]["detail"], "Small"))


def _checklist(story, r):
    story.append(P("Pre-signing diligence checklist", "H1"))
    story.append(P("This report is a screening tool. Nothing in it substitutes for these steps.", "Small"))
    rows = [["", "Check"]]
    for item in r["checklist"]:
        rows.append(["\u2610", item])
    story.append(_table(rows, [22, 446]))


# ------------------------------------------------------------------ widgets
def _banner(text, colour):
    t = Table([[Paragraph(f"<b>{_esc(text)}</b>",
                          ParagraphStyle("b", fontName="Helvetica-Bold", fontSize=10,
                                         textColor=colors.white, leading=13))]], colWidths=[468])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colour),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 7),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return t


def _kv(pairs):
    rows = [[Paragraph(_esc(k), S["CellBold"]), Paragraph(_esc(v), S["Cell"])] for k, v in pairs]
    t = Table(rows, colWidths=[168, 300])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
        ("BACKGROUND", (0, 0), (0, -1), PANEL),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def _table(rows, widths, highlight_row=None, threat_col=None, bold_last=False, bold_rows=None):
    data = []
    for i, row in enumerate(rows):
        style = "CellBold" if i == 0 else "Cell"
        data.append([Paragraph(_esc(c), S[style]) for c in row])
    t = Table(data, colWidths=widths, repeatRows=1)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafbfd")]),
    ]
    if highlight_row is not None and highlight_row < len(rows):
        cmds.append(("BACKGROUND", (0, highlight_row), (-1, highlight_row), colors.HexColor("#e6f3ec")))
    if threat_col is not None:
        for i, row in enumerate(rows[1:], 1):
            colour = THREAT_COLOUR.get(row[threat_col])
            if colour:
                cmds.append(("TEXTCOLOR", (threat_col, i), (threat_col, i), colour))
    if bold_last:
        cmds.append(("BACKGROUND", (0, len(rows) - 1), (-1, len(rows) - 1), colors.HexColor("#eef1f6")))
    for br in (bold_rows or []):
        if br < len(rows):
            cmds.append(("BACKGROUND", (0, br), (-1, br), colors.HexColor("#eef1f6")))
    t.setStyle(TableStyle(cmds))
    return t
