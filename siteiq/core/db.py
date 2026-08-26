"""Persistence: saved reports, comparison sets, background jobs, and the
operator's own store benchmarks used to calibrate the sales model."""
import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from ..config import DB_PATH

log = logging.getLogger("siteiq.db")
_lock = threading.Lock()


def conn():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def now():
    return datetime.now(timezone.utc).isoformat()


def init():
    with _lock, conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS reports(
            id TEXT PRIMARY KEY,
            created_at TEXT,
            address TEXT,
            concept TEXT,
            score REAL,
            verdict TEXT,
            confidence INTEGER,
            payload TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS comparisons(
            id TEXT PRIMARY KEY,
            created_at TEXT,
            concept TEXT,
            payload TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS jobs(
            id TEXT PRIMARY KEY,
            kind TEXT,
            created_at TEXT,
            status TEXT,
            progress INTEGER,
            step TEXT,
            result_id TEXT,
            error TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS benchmarks(
            id TEXT PRIMARY KEY,
            created_at TEXT,
            label TEXT,
            address TEXT,
            concept TEXT,
            actual_daily_sales REAL,
            monthly_rent REAL,
            sqft REAL,
            modeled_daily REAL,
            ratio REAL,
            notes TEXT
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at DESC)")


# ------------------------------------------------------------------ reports
def save_report(report: dict) -> str:
    rid = uuid.uuid4().hex[:12]
    report["id"] = rid
    with _lock, conn() as c:
        c.execute(
            "INSERT INTO reports(id, created_at, address, concept, score, verdict, confidence, payload)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (rid, now(), report.get("address", ""), report.get("concept", ""),
             report.get("score", 0), report.get("verdict", ""),
             report.get("confidence", {}).get("score", 0),
             json.dumps(report, default=str)),
        )
    return rid


def load_report(rid: str):
    with _lock, conn() as c:
        row = c.execute("SELECT payload FROM reports WHERE id=?", (rid,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["payload"])
    except ValueError:
        return None


def list_reports(limit=200):
    with _lock, conn() as c:
        rows = c.execute(
            "SELECT id, created_at, address, concept, score, verdict, confidence"
            " FROM reports ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def delete_report(rid):
    with _lock, conn() as c:
        c.execute("DELETE FROM reports WHERE id=?", (rid,))


# -------------------------------------------------------------- comparisons
def save_comparison(payload: dict) -> str:
    cid = uuid.uuid4().hex[:12]
    payload["id"] = cid
    with _lock, conn() as c:
        c.execute("INSERT INTO comparisons(id, created_at, concept, payload) VALUES(?,?,?,?)",
                  (cid, now(), payload.get("concept", ""), json.dumps(payload, default=str)))
    return cid


def load_comparison(cid: str):
    with _lock, conn() as c:
        row = c.execute("SELECT payload FROM comparisons WHERE id=?", (cid,)).fetchone()
    return json.loads(row["payload"]) if row else None


def list_comparisons(limit=50):
    with _lock, conn() as c:
        rows = c.execute(
            "SELECT id, created_at, concept FROM comparisons ORDER BY created_at DESC LIMIT ?",
            (limit,)).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------- jobs
def create_job(kind) -> str:
    jid = uuid.uuid4().hex[:12]
    with _lock, conn() as c:
        c.execute("INSERT INTO jobs(id, kind, created_at, status, progress, step)"
                  " VALUES(?,?,?,?,?,?)", (jid, kind, now(), "queued", 0, "Queued"))
    return jid


def update_job(jid, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with _lock, conn() as c:
        c.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), jid))


def get_job(jid):
    with _lock, conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------- benchmarks
def save_benchmark(**kw) -> str:
    bid = uuid.uuid4().hex[:12]
    with _lock, conn() as c:
        c.execute(
            "INSERT INTO benchmarks(id, created_at, label, address, concept,"
            " actual_daily_sales, monthly_rent, sqft, modeled_daily, ratio, notes)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (bid, now(), kw.get("label", ""), kw.get("address", ""), kw.get("concept", ""),
             kw.get("actual_daily_sales"), kw.get("monthly_rent"), kw.get("sqft"),
             kw.get("modeled_daily"), kw.get("ratio"), kw.get("notes", "")),
        )
    return bid


def list_benchmarks(concept=None):
    q = "SELECT * FROM benchmarks"
    args = ()
    if concept:
        q += " WHERE concept=?"
        args = (concept,)
    q += " ORDER BY created_at DESC"
    with _lock, conn() as c:
        rows = c.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def delete_benchmark(bid):
    with _lock, conn() as c:
        c.execute("DELETE FROM benchmarks WHERE id=?", (bid,))


def calibration_factor(concept):
    """Median ratio of actual to modeled sales across the operator's own stores.

    Returns (factor, sample_size). Factor is 1.0 with no benchmarks, and is
    clamped so one odd store cannot distort every future report.
    """
    rows = [r for r in list_benchmarks(concept)
            if r.get("ratio") and 0.2 < r["ratio"] < 5]
    if not rows:
        return 1.0, 0
    ratios = sorted(r["ratio"] for r in rows)
    mid = len(ratios) // 2
    median = ratios[mid] if len(ratios) % 2 else (ratios[mid - 1] + ratios[mid]) / 2
    return max(0.55, min(1.8, median)), len(ratios)
