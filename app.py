"""SiteIQ entrypoint.

Railway start command:
    gunicorn app:app

Local:
    python app.py
"""

import logging
import os
from pathlib import Path

from flask import Flask, render_template

from siteiq.config import (
    APP_VERSION,
    DATA_DIR,
    LOG_LEVEL,
    PORT,
    SECRET_KEY,
)
from siteiq.core import cache, db
from siteiq.web.routes import bp


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "siteiq" / "web" / "templates"
STATIC_DIR = BASE_DIR / "siteiq" / "web" / "static"


# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

log = logging.getLogger("siteiq")


# ---------------------------------------------------------
# Application factory
# ---------------------------------------------------------

def create_app():
    application = Flask(
        __name__,
        template_folder=str(TEMPLATE_DIR),
        static_folder=str(STATIC_DIR),
        static_url_path="/static",
    )

    # -----------------------------------------------------
    # Flask configuration
    # -----------------------------------------------------

    application.config["SECRET_KEY"] = SECRET_KEY
    application.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024
    application.config["JSON_SORT_KEYS"] = False

    # -----------------------------------------------------
    # Register routes
    # -----------------------------------------------------

    application.register_blueprint(bp)

    # -----------------------------------------------------
    # Error handlers
    # -----------------------------------------------------

    @application.errorhandler(404)
    def not_found(_error):
        return (
            render_template(
                "error.html",
                code=404,
                message="That page or report does not exist.",
            ),
            404,
        )

    @application.errorhandler(500)
    def server_error(error):
        log.exception("Unhandled SiteIQ error: %s", error)

        try:
            return (
                render_template(
                    "error.html",
                    code=500,
                    message="Something went wrong on our side. Try again.",
                ),
                500,
            )
        except Exception:
            # Prevent a missing/broken error template from causing
            # another server error.
            return (
                "SiteIQ encountered an internal error. Please try again.",
                500,
            )

    # -----------------------------------------------------
    # Response security headers
    # -----------------------------------------------------

    @application.after_request
    def add_security_headers(response):
        response.headers.setdefault(
            "X-Content-Type-Options",
            "nosniff",
        )
        response.headers.setdefault(
            "Referrer-Policy",
            "strict-origin-when-cross-origin",
        )
        response.headers.setdefault(
            "X-Frame-Options",
            "SAMEORIGIN",
        )
        return response

    # -----------------------------------------------------
    # Database and cache initialization
    # -----------------------------------------------------

    try:
        db.init()
        log.info("Database initialized successfully.")
    except Exception:
        log.exception("Database initialization failed.")
        raise

    try:
        cache.init()
        cache.purge(90)
        log.info("Cache initialized successfully.")
    except Exception:
        log.exception("Cache initialization failed.")
        raise

    # -----------------------------------------------------
    # Startup diagnostics
    # -----------------------------------------------------

    log.info("SiteIQ %s ready.", APP_VERSION)
    log.info("Base directory: %s", BASE_DIR)
    log.info("Template directory: %s", TEMPLATE_DIR)
    log.info("Static directory: %s", STATIC_DIR)
    log.info("Data directory: %s", DATA_DIR)

    if not TEMPLATE_DIR.exists():
        log.error(
            "Template directory does not exist: %s",
            TEMPLATE_DIR,
        )
    else:
        log.info(
            "Templates found: %s",
            sorted(
                file.name
                for file in TEMPLATE_DIR.glob("*.html")
            ),
        )

    if not STATIC_DIR.exists():
        log.error(
            "Static directory does not exist: %s",
            STATIC_DIR,
        )

    return application


# ---------------------------------------------------------
# Gunicorn entrypoint
# ---------------------------------------------------------

app = create_app()


# ---------------------------------------------------------
# Local development
# ---------------------------------------------------------

if __name__ == "__main__":
    runtime_port = int(os.getenv("PORT", PORT))

    app.run(
        host="0.0.0.0",
        port=runtime_port,
        debug=False,
    )
