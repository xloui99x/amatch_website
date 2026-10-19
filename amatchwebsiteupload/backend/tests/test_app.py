from __future__ import annotations

from typing import Any

import pytest
import requests
from flask.testing import FlaskClient

from amatch_checker.analysis import Report
from amatch_checker.app import Services, Settings, create_app
from amatch_checker.report_email import ResendConfig, build_email_html, render_score_chart
from amatch_checker.safe_fetch import FetchedPage, UnsafeUrlError

ORIGIN = "https://amatch.ch"


class Recorder:
    """Stands in for the network: serves a fixed page and records sent e-mails."""

    def __init__(self, html: str) -> None:
        self.html = html
        self.fetched: list[str] = []
        self.emails: list[tuple[str, Report]] = []
        self.fetch_error: Exception | None = None
        self.email_ok = True

    def fetch(self, url: str) -> FetchedPage:
        self.fetched.append(url)
        if self.fetch_error:
            raise self.fetch_error
        return FetchedPage(url=url, html=self.html)

    def send_email(self, to: str, report: Report, lang: str, config: ResendConfig) -> bool:
        self.emails.append((to, report))
        return self.email_ok


def make_client(recorder: Recorder, *, api_key: str = "test-key", **overrides: Any) -> FlaskClient:
    options: dict[str, Any] = {"allowed_origins": frozenset({ORIGIN}), **overrides}
    settings = Settings(
        resend=ResendConfig(api_key=api_key, sender="A Match <test@amatch.ch>"), **options
    )
    services = Services(fetch=recorder.fetch, send_email=recorder.send_email, clock=lambda: 0.0)
    return create_app(settings, services).test_client()


@pytest.fixture
def recorder(strong_ad: str) -> Recorder:
    return Recorder(strong_ad)


@pytest.fixture
def client(recorder: Recorder) -> FlaskClient:
    return make_client(recorder)


class TestCheckEndpoint:
    def test_returns_report_for_url_without_scheme(
        self, client: FlaskClient, recorder: Recorder
    ) -> None:
        response = client.get("/api/check?url=example.ch/job&lang=fr")
        assert response.status_code == 200
        body = response.get_json()
        assert body["overall"] == 100
        assert body["url"] == "https://example.ch/job"
        assert "Description du poste" in body["categories"]
        assert recorder.fetched == ["https://example.ch/job"]

    @pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.ch/x", "javascript://x"])
    def test_non_http_schemes_are_invalid(self, client: FlaskClient, url: str) -> None:
        response = client.get("/api/check", query_string={"url": url, "lang": "en"})
        assert response.status_code == 400
        assert response.get_json() == {"error": "Invalid URL"}

    def test_unknown_language_falls_back_to_german(self, client: FlaskClient) -> None:
        body = client.get("/api/check?url=example.ch&lang=xx").get_json()
        assert "Aufgabenbeschreibung" in body["categories"]

    def test_missing_url(self, client: FlaskClient) -> None:
        response = client.get("/api/check?lang=en")
        assert response.status_code == 400
        assert response.get_json() == {"error": "No URL provided"}

    def test_blocked_target_is_a_client_error(
        self, client: FlaskClient, recorder: Recorder
    ) -> None:
        recorder.fetch_error = UnsafeUrlError("private")
        response = client.get("/api/check?url=http://localhost:5432&lang=en")
        assert response.status_code == 400
        assert "security" in response.get_json()["error"]

    def test_unreachable_site_names_the_reason(
        self, client: FlaskClient, recorder: Recorder
    ) -> None:
        recorder.fetch_error = requests.exceptions.ConnectTimeout()
        response = client.get("/api/check?url=example.ch&lang=de")
        assert response.status_code == 502
        assert response.get_json() == {"error": "Stellenanzeige nicht erreichbar (ConnectTimeout)"}

    def test_rate_limit(self, recorder: Recorder) -> None:
        client = make_client(recorder, checks_per_minute=2)
        codes = [client.get("/api/check?url=example.ch").status_code for _ in range(3)]
        assert codes == [200, 200, 429]


class TestCors:
    def test_allowed_origin_is_echoed(self, client: FlaskClient) -> None:
        response = client.get("/api/health", headers={"Origin": ORIGIN})
        assert response.headers["Access-Control-Allow-Origin"] == ORIGIN

    def test_other_origins_get_no_cors_headers(self, client: FlaskClient) -> None:
        response = client.get("/api/health", headers={"Origin": "https://evil.example"})
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_wildcard_can_be_configured(self, recorder: Recorder) -> None:
        client = make_client(recorder, allowed_origins=frozenset({"*"}))
        response = client.get("/api/health", headers={"Origin": "https://any.example"})
        assert response.headers["Access-Control-Allow-Origin"] == "*"

    def test_preflight(self, client: FlaskClient) -> None:
        response = client.options("/api/send-report", headers={"Origin": ORIGIN})
        assert response.status_code == 204
        assert "POST" in response.headers["Access-Control-Allow-Methods"]


class TestSendReport:
    def post(self, client: FlaskClient, **body: Any) -> Any:
        return client.post("/api/send-report", json={"lang": "en", **body})

    def test_sends_report(self, client: FlaskClient, recorder: Recorder) -> None:
        response = self.post(client, email="kunde@firma.ch", url="example.ch/job")
        assert response.status_code == 200
        assert response.get_json() == {"status": "sent"}
        assert recorder.emails[0][0] == "kunde@firma.ch"

    @pytest.mark.parametrize("email", ["", "no-at-sign", "a@b", "two@@x.ch", "a b@c.ch"])
    def test_rejects_invalid_email(self, client: FlaskClient, email: str) -> None:
        assert self.post(client, email=email, url="example.ch").status_code == 400

    def test_requires_configuration(self, recorder: Recorder) -> None:
        client = make_client(recorder, api_key="")
        assert self.post(client, email="a@b.ch", url="x.ch").status_code == 503

    def test_provider_failure(self, client: FlaskClient, recorder: Recorder) -> None:
        recorder.email_ok = False
        assert self.post(client, email="a@b.ch", url="x.ch").status_code == 502

    def test_limits_emails_per_client(self, recorder: Recorder) -> None:
        client = make_client(recorder, emails_per_hour=1)
        assert self.post(client, email="a@b.ch", url="x.ch").status_code == 200
        assert self.post(client, email="a@b.ch", url="x.ch").status_code == 429
        assert len(recorder.emails) == 1


class TestEmailContent:
    def test_html_escapes_untrusted_values(self, weak_ad: str) -> None:
        from amatch_checker.analysis import analyze_html

        report = analyze_html(weak_ad, 'https://x.ch/"><script>alert(1)</script>', "en")
        html = build_email_html(report, "en")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_chart_is_a_png(self, strong_ad: str) -> None:
        from amatch_checker.analysis import analyze_html

        png = render_score_chart(analyze_html(strong_ad, "https://x.ch", "de"), "de")
        assert png.startswith(b"\x89PNG")
