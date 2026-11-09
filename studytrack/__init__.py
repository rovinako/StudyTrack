"""Application setup, shared template values, and request protection."""

from datetime import date
from pathlib import Path
import hmac
import os
import secrets
from flask import Flask, render_template, request, session, abort
from . import storage, ai
from .racket_bridge import executable
from .routes import web
from .learning import learning


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.update(
        SECRET_KEY=os.getenv("STUDYTRACK_SECRET") or secrets.token_hex(32),
        DATABASE=str(Path(app.instance_path) / "studytrack.sqlite"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=11 * 1024 * 1024,
        MAX_FORM_MEMORY_SIZE=256 * 1024,
        MAX_FORM_PARTS=40,
        TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"],
    )
    if config:
        app.config.update(config)
    app.teardown_appcontext(storage.close_db)
    with app.app_context():
        storage.db().executescript(storage.SCHEMA)

    @app.before_request
    def csrf_protection():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(24)
        if request.method == "POST" and not hmac.compare_digest(
            session["csrf"], request.form.get("csrf", "")
        ):
            abort(400, description="Your form expired. Reload the page and try again.")

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'"
        )
        return response

    @app.context_processor
    def common():
        return {
            "today": date.today().isoformat(),
            "ai_ready": ai.configured(),
            "engine": "Racket DSL" if executable() else "Python functional fallback",
        }

    @app.template_filter("grade")
    def grade(value):
        return "—" if value is None else f"{value:.1f}%"

    @app.errorhandler(ValueError)
    def calculation_error(error):
        return render_template("error.html", message=str(error)), 503

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def request_error(error):
        return render_template("error.html", message=error.description), error.code

    app.register_blueprint(web)
    app.register_blueprint(learning)
    return app
