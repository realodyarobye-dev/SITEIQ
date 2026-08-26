"""SQLite response cache.

Expensive third-party calls (Overpass especially) are cached by a hash of the
request so re-running a report, comparing 15 addresses on the same street, or
regenerating a PDF costs nothing.
"""
import hashlib
import json
import logging
import sqlite3
import threading
import time

from ..config import CACHE_TTL, DB_PATH

log = logging.getLogger("siteiq.cache")
_lock = threading.Lock()


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock, _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS cache(
            k TEXT PRIMARY KEY,
            bucket TEXT,
            payload TEXT,
            created REAL
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cache_created ON cache(created)")


def key(bucket, *parts):
    raw = bucket + "|" + "|".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def get(bucket, *parts):
    k = key(bucket, *parts)
    ttl = CACHE_TTL.get(bucket, 3600)
    try:
        with _lock, _conn() as c:
            row = c.execute("SELECT payload, created FROM cache WHERE k=?", (k,)).fetchone()
    except sqlite3.Error as exc:
        log.warning("cache read failed: %s", exc)
        return None
    if not row:
        return None
    if time.time() - row["created"] > ttl:
        return None
    try:
        return json.loads(row["payload"])
    except ValueError:
        return None


def put(bucket, value, *parts):
    if value is None:
        return value
    k = key(bucket, *parts)
    try:
        with _lock, _conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO cache(k, bucket, payload, created) VALUES(?,?,?,?)",
                (k, bucket, json.dumps(value, default=str), time.time()),
            )
    except (sqlite3.Error, TypeError) as exc:
        log.warning("cache write failed: %s", exc)
    return value


def cached(bucket, parts, producer):
    """get-or-produce. `producer` is a zero-arg callable."""
    hit = get(bucket, *parts)
    if hit is not None:
        log.debug("cache hit %s", bucket)
        return hit
    value = producer()
    if value is not None:
        put(bucket, value, *parts)
    return value


def purge(older_than_days=90):
    cutoff = time.time() - older_than_days * 86400
    try:
        with _lock, _conn() as c:
            c.execute("DELETE FROM cache WHERE created < ?", (cutoff,))
    except sqlite3.Error:
        pass
