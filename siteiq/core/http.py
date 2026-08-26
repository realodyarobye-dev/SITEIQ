"""One HTTP client for every provider: shared session, sane timeouts,
bounded retries with backoff, and never an unhandled exception escaping."""
import logging
import time

import requests
from requests.adapters import HTTPAdapter

from ..config import HTTP_RETRIES, HTTP_TIMEOUT, USER_AGENT

log = logging.getLogger("siteiq.http")

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
_adapter = HTTPAdapter(pool_connections=20, pool_maxsize=40)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)

RETRY_STATUS = {429, 500, 502, 503, 504}


def request(method, url, *, timeout=None, retries=None, **kwargs):
    """Returns a Response or None. Never raises."""
    timeout = timeout or HTTP_TIMEOUT
    retries = HTTP_RETRIES if retries is None else retries
    delay = 0.8
    last = None
    for attempt in range(retries + 1):
        try:
            resp = _session.request(method, url, timeout=timeout, **kwargs)
            if resp.status_code in RETRY_STATUS and attempt < retries:
                log.warning("%s %s -> %s, retrying", method, url, resp.status_code)
                time.sleep(delay)
                delay *= 2
                continue
            return resp
        except requests.RequestException as exc:
            last = exc
            log.warning("%s %s failed (%s/%s): %s", method, url, attempt + 1, retries + 1, exc)
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
    if last:
        log.error("%s %s exhausted retries: %s", method, url, last)
    return None


def get_json(url, **kwargs):
    resp = request("GET", url, **kwargs)
    return _json(resp, url)


def post_json(url, **kwargs):
    resp = request("POST", url, **kwargs)
    return _json(resp, url)


def get_bytes(url, **kwargs):
    resp = request("GET", url, **kwargs)
    if resp is not None and resp.ok:
        return resp.content
    return None


def _json(resp, url):
    if resp is None:
        return None
    if not resp.ok:
        log.warning("%s returned HTTP %s", url, resp.status_code)
        return None
    try:
        return resp.json()
    except ValueError:
        log.warning("%s returned non-JSON body", url)
        return None
