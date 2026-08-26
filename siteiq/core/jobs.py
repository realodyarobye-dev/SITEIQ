"""Background job runner.

A full analysis touches several APIs and can take 15-40 seconds; comparing 20
addresses takes minutes. Running that inside a web request means the browser
spins and the server eventually kills the worker. Instead every analysis becomes
a job: the page returns instantly, then polls for progress.
"""
import logging
import threading
import traceback

from . import db

log = logging.getLogger("siteiq.jobs")
_pool = []


class Progress:
    """Handed to the worker so it can report what it is doing right now."""

    def __init__(self, job_id):
        self.job_id = job_id

    def __call__(self, percent, step):
        db.update_job(self.job_id, progress=int(max(0, min(99, percent))), step=str(step)[:160])
        log.info("job %s %s%% %s", self.job_id, int(percent), step)


def start(kind, target, *args, **kwargs):
    """target(progress, *args, **kwargs) must return the id of a saved result."""
    jid = db.create_job(kind)

    def run():
        progress = Progress(jid)
        db.update_job(jid, status="running", progress=2, step="Starting")
        try:
            result_id = target(progress, *args, **kwargs)
            db.update_job(jid, status="done", progress=100, step="Complete", result_id=result_id)
        except Exception as exc:  # noqa: BLE001 - jobs must never crash the app
            log.error("job %s failed: %s\n%s", jid, exc, traceback.format_exc())
            db.update_job(jid, status="error", step="Failed", error=str(exc)[:500])

    t = threading.Thread(target=run, daemon=True, name=f"siteiq-job-{jid}")
    t.start()
    _pool.append(t)
    _pool[:] = [x for x in _pool if x.is_alive()]
    return jid


def status(jid):
    job = db.get_job(jid)
    if not job:
        return None
    return {
        "id": job["id"],
        "kind": job["kind"],
        "status": job["status"],
        "progress": job["progress"] or 0,
        "step": job["step"] or "",
        "result_id": job["result_id"],
        "error": job["error"],
    }
