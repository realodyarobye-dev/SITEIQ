# SiteIQ 6.0 — NYC retail location intelligence

You enter an address. SiteIQ investigates the block, the competitors, who walks
past, what used to occupy that storefront, what it could realistically sell and
what could kill it — then tells you whether it would put $500,000 there.

**To deploy it, read [DEPLOY.md](DEPLOY.md).** That guide assumes no coding
knowledge. This file explains what was wrong with v5 and what the rebuild does.

---

## Audit of the version you sent

The v5 app was 217 lines in one file. It ran, and some of it was worth keeping —
the Overpass and Census calls, the Google Places integration, the SQLite report
storage and the general shape of the report. The following were real problems.

**The sales model produced numbers that could not happen.** Daily sales were
`(100 + 4.5 × score) × ticket`, making sales a pure function of the score. A
mid-scoring deli modeled to $6,660/day, a good one to over $8,000/day, with no
upper bound tied to anything physical.

**The profit formula was worse.** It took 27% of monthly sales, subtracted rent,
and subtracted a flat $6,500 for everything else. Labour was not a percentage of
sales and had no floor for the hours you keep. There was no delivery commission,
no card processing, no COGS by category. On a mid-range deli it returned roughly
$54,000/month in profit. That number could get somebody badly hurt.

**Comparison mode could not work on Railway.** It analysed up to 20 addresses
serially inside a single web request, each doing a 25-second Overpass call.
Gunicorn's default worker timeout is 30 seconds. It would have returned 502
every time with more than one address.

**Missing data silently became zero, then became conclusions.** `pop = cen.get('population') or 3000`
substituted an invented 3,000 residents whenever the Census lookup failed, and
that invented number flowed into activity, demand, score and sales without ever
being labelled.

**No caching.** Every page load re-hit Nominatim and Overpass, which both
publish usage policies that this would violate at any real volume.

**Competition saturated immediately.** `max(20, 90 - len(comp) * 3)` with Google
capped at 20 results meant 20 competitors and 40 competitors scored identically.

**Security and correctness gaps.** The `/saved` page interpolated addresses into
HTML with f-strings (XSS). The `/photo` endpoint concatenated an unvalidated
user parameter into a Google URL. There was a `stable()` hash-to-random helper
left in the file, unused — the signature of previously fabricated values.

**Missing outright:** the map, block analysis, customer profiles, opportunity
detection, red flags, data confidence, source transparency, business longevity,
weekday/weekend splits, and input validation. The PDF was two pages of default
ReportLab styles; the PPTX was five slides of plain text boxes.

---

## What the rebuild does differently

### Sales are built from the bottom up, then capped by physics

Instead of scaling a score, SiteIQ estimates each customer pool that passes
within capture range, applies a capture rate, and adjusts for how much
competition splits it:

```
residents 11,460 × 13.0% base → 5.6% after competition →  642 sales/day
commuters  7,000 ×  2.4% base → 1.0% after competition →   72 sales/day
office     2,160 × 10.0% base → 4.3% after competition →   93 sales/day
...
```

Then a physical ceiling is applied. A 1,500 sq ft deli has about two service
positions; each clears roughly 15 customers an hour once peaks and dead hours
are averaged; open 24 hours that caps the store near 720 transactions a day no
matter how much demand walks past. Demand above the ceiling is lost to the
queue, not banked. This is what stops a well-located site from modeling to
$23,000/day, and it makes square footage and hours matter the way they actually
do.

Every pool, capture rate and modifier is shown in the report. You can disagree
with any single line and see exactly what it changes.

### The P&L is a real street-retail P&L

COGS by concept, labour as the greater of a percentage or the cost of physically
covering the hours you keep, **third-party delivery commission broken out
separately** at a blended rate, card processing on the in-store share, rent, and
itemised fixed costs. Break-even is solved for, in dollars per day.

### Nothing missing is treated as zero

Every conclusion carries an evidence tier — OBSERVED, VERIFIED, MODELED,
INFERRED or UNAVAILABLE — and those roll into a Data Confidence score. When the
Census lookup fails, the report says so and the confidence score drops. It never
invents 3,000 residents. With every provider down, the app still produces a
report; it scores 1/100 with confidence 30 and tells you why, which is the
honest answer.

Modeled daypart scores are labelled modeled in every place they appear. SiteIQ
has no foot-traffic feed and says so rather than implying it counted anybody.

### NYC Open Data does what no map API can

Public city records answer the questions a map cannot:

- **What was in this storefront** — health inspections and business licences at
  the exact building and street, with the years each name appears.
- **Does this block hold tenants** — how many nearby food businesses are still
  active, how many lasted eight years, how many closed within two.
- **How long has a competitor been there** — earliest licence or inspection on
  record, reported as *"Confirmed operating since at least 2013"*, never as an
  invented opening date.
- **How many people actually live on this block** — PLUTO residential unit
  counts, which beat estimating from tract density.
- **Construction** — DOB permits on the street.

### Long work runs in the background

Analyses and comparisons are jobs. The page returns instantly and polls for
progress with a real status line. Comparison handles 20 addresses without
timing out. Gunicorn is configured with a 180-second timeout and threads.

---

## Architecture

```
app.py                       entrypoint — Railway runs: gunicorn app:app
siteiq/
  config.py                  env vars, concept economics, dataset IDs
  core/
    provenance.py            Fact, ConfidenceLedger, SourceRegistry
    http.py                  shared session, timeouts, bounded retries
    cache.py                 SQLite response cache with per-source TTLs
    geo.py                   distance, bearing, street-axis inference
    db.py                    reports, comparisons, jobs, calibration
    jobs.py                  background runner with progress
  providers/                 one adapter per source, each optional
    geocode.py  census.py  overpass.py  google_places.py  nyc.py
  engine/
    classify.py              OSM/Google tags → operator categories
    competitors.py           three-axis threat scoring with reasoning
    block.py                 THE BLOCK — left, right, across, corner
    generators.py            demand generators ranked per concept
    customers.py             who walks in, what they buy
    dayparts.py              8 windows, weekday/weekend, labelled modeled
    sales.py                 bottom-up model, capacity ceiling, P&L
    rent.py                  estimation band + occupancy assessment
    opportunities.py         multi-signal gap detection
    risks.py                 severity-graded red flags
    scoring.py               weighted score, verdict, the $500K answer
    analyze.py               parallel orchestration
    compare.py               ranking and the single recommendation
  exports/
    pdf.py                   designed multi-page consulting report
    pptx_export.py           15 designed slides
    comparison_pdf.py
  web/
    routes.py  templates/  static/siteiq.css
smoketest.py                 offline end-to-end test with stubbed providers
```

Adding a provider means writing one adapter file and one line in `analyze.py`.
Nothing else knows where data came from.

---

## Which API keys matter

| Key | What it adds | Importance |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | Competitor ratings, review counts, hours, 24-hour status, photos, Maps links, websites, phones, price levels, Street View | **Transformative.** Without it competitor intelligence is about half of what it should be. |
| `NYC_APP_TOKEN` | Nothing new — raises the rate limit on city records so bulk comparisons are not throttled | Useful, free |
| `CONTACT_EMAIL` | Identifies the app to OpenStreetMap's free geocoder as their policy asks | Do this |
| `SECRET_KEY` | Signs session data | Do this |

Not wired up, because none have free tiers, but the provider layer is built to
take them: **Placer.ai / Unacast / SafeGraph** for real measured foot traffic
(the one gap SiteIQ genuinely cannot close for free), **CoStar / Crexi** for
actual asking rents, **Walk Score**, **Yelp Fusion**.

---

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

46 unit tests cover the engine's actual decision logic — the capacity
ceiling, store calibration, the two-signal opportunity gate, and the
critical-risk verdict override. `requirements-dev.txt` is never installed in
production; Railway only ever installs `requirements.txt`.

`python3 smoketest.py` runs the whole pipeline offline with stubbed providers
and generates a PDF, a PPTX, a comparison and both comparison exports. It also
covers the total-failure path where every provider returns nothing.

See [MERGE_NOTES.md](MERGE_NOTES.md) for what was combined from a second
build of this app and why.

---

## What SiteIQ will not do

It will not invent a foot-traffic count, an opening date, a rent, a sales
figure, a photograph or a business that it cannot source. Where it estimates, it
says ESTIMATE. Where it models, it says MODELED. Where it does not know, it says
UNAVAILABLE and lets the confidence score fall.

A sophisticated-looking wrong report is worse than an honest incomplete one,
particularly at $500,000.
