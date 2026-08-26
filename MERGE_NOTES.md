# Merge notes: SiteIQ v6 (this build) + ChatGPT's SITEIQ2

You asked for both builds combined into one app. Here is exactly what that
meant in practice, and why — same honesty standard the app itself holds to.

## The starting point

Both builds were audited side by side (full audit further down this chat).
The short version: this build's engine was ahead on every measure that
determines whether the report can be trusted with real money — a sales model
with a physical capacity ceiling instead of an unbounded score multiplier,
a five-dataset NYC Open Data layer (storefront tenant history, block churn,
PLUTO, DOB permits) instead of one dataset matched by exact business name,
real street-axis geometry for THE BLOCK instead of that section being left as
`UNAVAILABLE` placeholders, background jobs instead of a comparison mode that
blocks the HTTP request for up to 20 addresses, and a store-calibration
feature with no equivalent in the other build at all.

There was exactly one thing the other build did that this one didn't:
**an actual automated test suite.** This build had an integration smoke test
(`smoketest.py`) that exercises the whole pipeline with stubbed providers, but
no unit tests against individual engine functions. That is a real gap and a
real strength of the other build.

## What got merged in

**A pytest suite covering the engine's actual decision logic** — 46 tests
across 9 files in `tests/`, run with `pytest` (see `requirements-dev.txt`).
Not a token gesture: it specifically tests the properties that matter most
for a $500K decision tool —

- the capacity ceiling actually caps sales under an artificially extreme
  demand signal (`test_sales.py`) — this is the exact failure mode the
  original app had with no test coverage at all
- store calibration measurably shifts the estimate, and outlier benchmark
  entries are excluded or clamped rather than distorting every future report
  (`test_sales.py`, `test_calibration_db.py`)
- opportunities require two independent signals, not one — the same demand
  signal that triggers an opportunity when no 24-hour competitor exists must
  NOT trigger it once a competitor already covers that window
  (`test_opportunities.py`)
- a critical red flag overrides the verdict even when every component score
  is otherwise strong, and a conservative-case loss blocks a "TAKE IT"
  verdict (`test_scoring.py`)
- missing data produces `UNAVAILABLE`, never a silently invented number
  (`test_provenance.py`)

Building this suite caught two real bugs in the tests themselves before they
shipped — a distance-window mismatch in a geometry test and a wrong
assumption about which stage of the calibration clamp an outlier ratio would
hit. Both are visible in this repo's history as separate, honest fixes rather
than papered over, which is the same standard applied to the app's own
data — say what's actually true, not what looks complete.

**Nothing else was ported.** The other build's engine modules (`scoring.py`,
`analysis.py`, `nyc_open_data.py`, etc.) are a strict subset of what this
build already does, so copying them in would have made the app worse, not
combined it with something better. Where the other build made a genuinely
different design choice — showing `UNAVAILABLE` for profit instead of a
labeled estimate when rent isn't entered — that's a legitimate trade-off
already covered in the audit, not a bug to fix by importing their code.

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

`requirements-dev.txt` pulls in `requirements.txt` plus `pytest` — production
deploys on Railway never install it, so it adds nothing to the running app.
