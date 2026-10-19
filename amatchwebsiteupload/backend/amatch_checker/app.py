"""Flask application: the HTTP layer around the analysis.

Endpoints
---------
GET  /api/check?url=…&lang=de|fr|en   → JSON report
POST /api/send-report {email, url, lang} → e-mails the report
GET  /api/health                       → liveness probe
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

import requests
from flask import Flask, Response, jsonify, request

from .analysis import Report, analyze_html
from .i18n import ERRORS, Lang, resolve_lang
from .rate_limit import RateLimiter
from .report_email import ResendConfig, send_report_email
from .safe_fetch import UnsafeUrlError, fetch_page

log = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEFAULT_ORIGINS = (
    "https://amatch.ch",
    "https://www.amatch.ch",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
)


@dataclass(frozen=True)
class Settings:
    resend: ResendConfig
    allowed_origins: frozenset[str]
    checks_per_minute: int = 20
    emails_per_hour: int = 5

    @classmethod
    def from_env(cls) -> Settings:
        origins = os.environ.get("AMATCH_ALLOWED_ORIGINS")
        return cls(
            resend=ResendConfig(
                api_key=os.environ.get("RESEND_API_KEY", ""),
                sender=os.environ.get("RESEND_FROM", "A Match <onboarding@resend.dev>"),
            ),
            allowed_origins=frozenset(
                o.strip() for o in (origins.split(",") if origins else DEFAULT_ORIGINS) if o.strip()
            ),
        )


class CheckError(Exception):
    """A user-facing failure with an HTTP status and a localized message."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class Services:
    """Collaborators the routes use; replaceable in tests."""

    fetch: Any = fetch_page
    send_email: Any = send_report_email
    clock: Any = field(default=time.perf_counter)


SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.\-]*://", re.IGNORECASE)


def normalize_url(raw: str) -> str:
    """Adds https:// to bare domains ("firma.ch/jobs"); keeps explicit schemes."""
    url = raw.strip()
    return url if SCHEME_RE.match(url) else "https://" + url


def run_check(raw_url: str, lang: Lang, services: Services) -> Report:
    url = normalize_url(raw_url)
    errors = ERRORS[lang]
    if not re.match(r"^https?://[^/\s]+", url, re.IGNORECASE):
        raise CheckError(400, errors["invalid_url"])

    started = services.clock()
    try:
        page = services.fetch(url)
    except UnsafeUrlError as exc:
        log.warning("Blocked check of %s: %s", url, exc)
        raise CheckError(400, errors["blocked_url"]) from exc
    except requests.exceptions.RequestException as exc:
        raise CheckError(502, errors["unreachable"].format(reason=type(exc).__name__)) from exc
    elapsed = services.clock() - started

    return analyze_html(page.html, url, lang, load_time=elapsed)


def create_app(settings: Settings | None = None, services: Services | None = None) -> Flask:
    settings = settings or Settings.from_env()
    services = services or Services()
    check_limiter = RateLimiter(settings.checks_per_minute, 60)
    email_limiter = RateLimiter(settings.emails_per_hour, 3600)

    app = Flask(__name__)
    app.json.ensure_ascii = False  # type: ignore[attr-defined, unused-ignore]

    def client_id() -> str:
        # Behind Render's proxy the client is the first X-Forwarded-For entry.
        forwarded = request.headers.get("X-Forwarded-For", "")
        return forwarded.split(",")[0].strip() or (request.remote_addr or "unknown")

    def error(status: int, message: str) -> tuple[Response, int]:
        return jsonify({"error": message}), status

    @app.after_request
    def add_cors_headers(response: Response) -> Response:
        origin = request.headers.get("Origin")
        if "*" in settings.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = "*"
        elif origin and origin in settings.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        else:
            return response
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @app.route("/api/check", methods=["GET", "OPTIONS"])
    def api_check() -> Any:
        if request.method == "OPTIONS":
            return "", 204
        lang = resolve_lang(request.args.get("lang"))
        raw_url = request.args.get("url", "")
        if not raw_url:
            return error(400, ERRORS[lang]["missing_url"])
        if not check_limiter.allow(client_id()):
            return error(429, ERRORS[lang]["rate_limited"])
        try:
            return jsonify(run_check(raw_url, lang, services).to_dict())
        except CheckError as exc:
            return error(exc.status, exc.message)

    @app.route("/api/send-report", methods=["POST", "OPTIONS"])
    def api_send_report() -> Any:
        if request.method == "OPTIONS":
            return "", 204
        data = request.get_json(silent=True) or {}
        lang = resolve_lang(data.get("lang"))
        errors = ERRORS[lang]

        if not settings.resend.enabled:
            return error(503, errors["not_configured"])
        to_email = str(data.get("email") or "").strip()
        if not EMAIL_RE.match(to_email):
            return error(400, errors["invalid_email"])
        raw_url = str(data.get("url") or "")
        if not raw_url:
            return error(400, errors["missing_url"])
        if not email_limiter.allow(client_id()):
            return error(429, errors["rate_limited"])

        try:
            report = run_check(raw_url, lang, services)
        except CheckError as exc:
            return error(exc.status, exc.message)

        try:
            sent = services.send_email(to_email, report, lang, settings.resend)
        except requests.exceptions.RequestException:
            log.exception("Sending the report e-mail failed")
            sent = False
        if not sent:
            return error(502, errors["send_failed"])
        return jsonify({"status": "sent"})

    @app.route("/api/health")
    def health() -> Any:
        return jsonify({"status": "ok"})

    return app
