"""SiteIQ entrypoint.

Railway start command:  gunicorn app:app
Local:                  python app.py
"""
import logging
import os

from flask import Flask, render_template

from siteiq.config import APP_VERSION, DATA_DIR, LOG_LEVEL, PORT, SECRET_KEY
from siteiq.core import cache, db
from siteiq.web.routes import bp

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("siteiq")


def create_app():
    application = Flask(
        __name__,
        template_folder="siteiq/web/templates",
        static_folder="siteiq/web/static",
    )
    application.config["SECRET_KEY"] = SECRET_KEY
    application.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024
    application.config["JSON_SORT_KEYS"] = False
    application.register_blueprint(bp)

    @application.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", code=404,
                               message="That page or report does not exist."), 404

    @application.errorhandler(500)
    def server_error(e):
        log.error("unhandled error: %s", e)
        return render_template("error.html", code=500,
                               message="Something went wrong on our side. Try again."), 500

    @application.after_request
    def headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp

    db.init()
    cache.init()
    cache.purge(90)
    log.info("SiteIQ %s ready. Data directory: %s", APP_VERSION, DATA_DIR)
    return application


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", PORT)), debug=False)
