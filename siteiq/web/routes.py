"""Flask routes."""
import io
import logging
import re

from flask import (Blueprint, abort, jsonify, redirect, render_template, request,
                   send_file, url_for)

from ..config import CONCEPTS, DEFAULT_CONCEPT, HAS_GOOGLE, NYC_APP_TOKEN
from ..core import db, jobs
from ..engine import compare as compare_engine
from ..engine.analyze import analyse
from ..exports import comparison_pdf, pdf, pptx_export
from ..providers import google_places

log = logging.getLogger("siteiq.web")
bp = Blueprint("web", __name__)

MAX_ADDRESS = 220


# ------------------------------------------------------------------ helpers
def _clean_address(value):
    value = (value or "").strip()
    value = re.sub(r"[\x00-\x1f\x7f]", "", value)[:MAX_ADDRESS]
    return value


def _number(value, minimum=0, maximum=10_000_000):
    if value in (None, ""):
        return None
    try:
        v = float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None
    if v < minimum or v > maximum:
        return None
    return v


def _inputs(form):
    out = {
        "rent": _number(form.get("rent"), 0, 500_000),
        "sqft": _number(form.get("sqft"), 80, 200_000),
        "hours": (form.get("hours") or "").strip()[:60] or None,
        "buildout": _number(form.get("buildout"), 0, 20_000_000),
        "wage": _number(form.get("wage"), 10, 100),
    }
    commission = _number(form.get("delivery_commission"), 0, 60)
    if commission:
        out["delivery_commission"] = commission / 100.0
    return {k: v for k, v in out.items() if v is not None}


def _concept(form):
    c = (form.get("concept") or DEFAULT_CONCEPT).strip()
    return c if c in CONCEPTS else DEFAULT_CONCEPT


def _photos(report):
    """Fetch imagery for exports. Never blocks the report if it fails."""
    out = {}
    if not HAS_GOOGLE:
        return out
    try:
        img, _meta = google_places.streetview(report["lat"], report["lon"], size="640x400")
        if img:
            out["streetview"] = img
    except Exception as exc:  # noqa: BLE001
        log.warning("street view fetch failed: %s", exc)
    for c in report["competitors"][:6]:
        if not c.get("photo"):
            continue
        try:
            data = google_places.photo_bytes(c["photo"], max_width=520)
            if data:
                out[f"comp_{c.get('id') or c['name']}"] = data
        except Exception as exc:  # noqa: BLE001
            log.warning("competitor photo failed: %s", exc)
    return out


# -------------------------------------------------------------------- pages
@bp.route("/")
def home():
    return render_template("home.html", concepts=CONCEPTS, default_concept=DEFAULT_CONCEPT,
                           google_enabled=HAS_GOOGLE, nyc_enabled=bool(NYC_APP_TOKEN),
                           recent=db.list_reports(8))


@bp.route("/analyze", methods=["POST"])
def start_analysis():
    address = _clean_address(request.form.get("address"))
    if not address:
        return render_template("home.html", concepts=CONCEPTS, default_concept=DEFAULT_CONCEPT,
                               google_enabled=HAS_GOOGLE, recent=db.list_reports(8),
                               error="Enter an address to analyse."), 400
    concept = _concept(request.form)
    inputs = _inputs(request.form)

    def work(progress):
        report = analyse(address, concept, inputs, progress)
        if not report:
            raise ValueError(f"Could not locate the address: {address}")
        return db.save_report(report)

    jid = jobs.start("analysis", work)
    return redirect(url_for("web.running", job_id=jid))


@bp.route("/running/<job_id>")
def running(job_id):
    job = jobs.status(job_id)
    if not job:
        abort(404)
    return render_template("running.html", job=job)


@bp.route("/api/job/<job_id>")
def job_status(job_id):
    job = jobs.status(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    if job["status"] == "done" and job["result_id"]:
        endpoint = "web.comparison" if job["kind"] == "comparison" else "web.report"
        param = {"cid": job["result_id"]} if job["kind"] == "comparison" else {"rid": job["result_id"]}
        job["redirect"] = url_for(endpoint, **param)
    return jsonify(job)


@bp.route("/report/<rid>")
def report(rid):
    r = db.load_report(rid)
    if not r:
        abort(404)
    return render_template("report.html", r=r, google_enabled=HAS_GOOGLE)


@bp.route("/report/<rid>/delete", methods=["POST"])
def delete_report(rid):
    db.delete_report(rid)
    return redirect(url_for("web.saved"))


@bp.route("/saved")
def saved():
    return render_template("saved.html", reports=db.list_reports(200),
                           comparisons=db.list_comparisons(30))


# ----------------------------------------------------------------- compare
@bp.route("/compare", methods=["GET", "POST"])
def compare():
    if request.method == "GET":
        return render_template("compare.html", concepts=CONCEPTS, default_concept=DEFAULT_CONCEPT)
    raw = request.form.get("addresses") or ""
    addresses = [_clean_address(a) for a in raw.splitlines()]
    addresses = [a for a in addresses if a][:compare_engine.MAX_ADDRESSES]
    if len(addresses) < 2:
        return render_template("compare.html", concepts=CONCEPTS, default_concept=DEFAULT_CONCEPT,
                               error="Enter at least two addresses, one per line."), 400
    concept = _concept(request.form)
    inputs = _inputs(request.form)

    def work(progress):
        result = compare_engine.run(addresses, concept, inputs, progress)
        if not result["rows"]:
            raise ValueError("None of those addresses could be located.")
        return db.save_comparison(result)

    jid = jobs.start("comparison", work)
    return redirect(url_for("web.running", job_id=jid))


@bp.route("/comparison/<cid>")
def comparison(cid):
    c = db.load_comparison(cid)
    if not c:
        abort(404)
    return render_template("comparison.html", c=c)


# ----------------------------------------------------------------- exports
@bp.route("/report/<rid>/pdf")
def report_pdf(rid):
    r = db.load_report(rid)
    if not r:
        abort(404)
    data = pdf.build(r, _photos(r))
    return send_file(io.BytesIO(data), mimetype="application/pdf", as_attachment=True,
                     download_name=_filename(r, "pdf"))


@bp.route("/report/<rid>/pptx")
def report_pptx(rid):
    r = db.load_report(rid)
    if not r:
        abort(404)
    data = pptx_export.build(r, _photos(r))
    return send_file(
        io.BytesIO(data),
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        as_attachment=True, download_name=_filename(r, "pptx"))


@bp.route("/comparison/<cid>/pdf")
def comparison_pdf_route(cid):
    c = db.load_comparison(cid)
    if not c:
        abort(404)
    data = comparison_pdf.build(c)
    return send_file(io.BytesIO(data), mimetype="application/pdf", as_attachment=True,
                     download_name="siteiq_comparison.pdf")


@bp.route("/comparison/<cid>/pptx")
def comparison_pptx(cid):
    c = db.load_comparison(cid)
    if not c:
        abort(404)
    data = pptx_export.build_comparison(c)
    return send_file(
        io.BytesIO(data),
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        as_attachment=True, download_name="siteiq_comparison.pptx")


def _filename(r, ext):
    slug = re.sub(r"[^A-Za-z0-9]+", "_", r["address"])[:48].strip("_") or "location"
    return f"siteiq_{slug}.{ext}"


# ------------------------------------------------------------- photo proxy
@bp.route("/media/place-photo")
def place_photo():
    """Proxies a Google Places photo so the API key never reaches the browser."""
    name = request.args.get("name", "")
    if not name.startswith("places/") or "/photos/" not in name:
        abort(400)
    data = google_places.photo_bytes(name, max_width=int(request.args.get("w", 640)))
    if not data:
        abort(404)
    resp = send_file(io.BytesIO(data), mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@bp.route("/media/streetview")
def streetview():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    heading = request.args.get("heading", type=float)
    if lat is None or lon is None:
        abort(400)
    img, _meta = google_places.streetview(lat, lon, heading, size="640x400")
    if not img:
        abort(404)
    resp = send_file(io.BytesIO(img), mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


# -------------------------------------------------------------- benchmarks
@bp.route("/calibrate", methods=["GET", "POST"])
def calibrate():
    """Teach SiteIQ using your own stores: enter a store you already operate and
    its real daily sales, and future estimates for that concept get corrected."""
    if request.method == "GET":
        return render_template("calibrate.html", concepts=CONCEPTS,
                               default_concept=DEFAULT_CONCEPT,
                               benchmarks=db.list_benchmarks())

    address = _clean_address(request.form.get("address"))
    actual = _number(request.form.get("actual_daily_sales"), 1, 500_000)
    if not address or not actual:
        return render_template("calibrate.html", concepts=CONCEPTS,
                               default_concept=DEFAULT_CONCEPT,
                               benchmarks=db.list_benchmarks(),
                               error="Enter the store address and its actual average daily sales."), 400
    concept = _concept(request.form)
    inputs = _inputs(request.form)

    def work(progress):
        progress(20, "Analysing your existing store")
        report = analyse(address, concept, inputs, progress)
        if not report:
            raise ValueError("Could not locate that address.")
        modeled = report["sales"]["scenarios"]["Realistic"]["daily"]
        db.save_benchmark(
            label=(request.form.get("label") or address)[:80], address=address, concept=concept,
            actual_daily_sales=actual, monthly_rent=inputs.get("rent"), sqft=inputs.get("sqft"),
            modeled_daily=modeled, ratio=(actual / modeled) if modeled else None,
            notes=(request.form.get("notes") or "")[:400])
        return db.save_report(report)

    jid = jobs.start("analysis", work)
    return redirect(url_for("web.running", job_id=jid))


@bp.route("/calibrate/<bid>/delete", methods=["POST"])
def delete_benchmark(bid):
    db.delete_benchmark(bid)
    return redirect(url_for("web.calibrate"))


@bp.route("/setup")
def setup():
    return render_template("setup.html", google_enabled=HAS_GOOGLE,
                           nyc_token=bool(NYC_APP_TOKEN))


@bp.route("/health")
def health():
    return jsonify({"status": "ok", "google": HAS_GOOGLE})
