from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import pytest
import requests

from amatch_checker.safe_fetch import (
    MAX_BYTES,
    UnsafeUrlError,
    fetch_page,
    is_public_ip,
    validate_url,
)

PUBLIC = "93.184.215.14"


def resolver_for(mapping: dict[str, list[str]]) -> Callable[[str], list[str]]:
    def resolve(host: str) -> list[str]:
        return mapping.get(host, [PUBLIC])

    return resolve


class TestIsPublicIp:
    @pytest.mark.parametrize(
        "address",
        ["127.0.0.1", "10.0.0.5", "172.16.3.4", "192.168.1.1", "169.254.169.254", "0.0.0.0",
         "100.64.0.1", "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1", "224.0.0.1"],
    )  # fmt: skip
    def test_blocks_internal_addresses(self, address: str) -> None:
        assert not is_public_ip(address)

    @pytest.mark.parametrize("address", [PUBLIC, "8.8.8.8", "2606:4700:4700::1111"])
    def test_allows_public_addresses(self, address: str) -> None:
        assert is_public_ip(address)


class TestValidateUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://example.ch/",
            "gopher://example.ch/",
            "https://user:pw@example.ch/",
            "https://example.ch:8080/",
            "http://",
        ],
    )
    def test_rejects_unsafe_shapes(self, url: str) -> None:
        with pytest.raises(UnsafeUrlError):
            validate_url(url, resolver_for({}))

    def test_rejects_hosts_resolving_to_private_ips(self) -> None:
        resolver = resolver_for({"intranet.example.ch": ["10.1.2.3"]})
        with pytest.raises(UnsafeUrlError):
            validate_url("https://intranet.example.ch/", resolver)

    def test_rejects_if_any_resolved_ip_is_private(self) -> None:
        resolver = resolver_for({"mixed.example.ch": [PUBLIC, "127.0.0.1"]})
        with pytest.raises(UnsafeUrlError):
            validate_url("https://mixed.example.ch/", resolver)

    def test_unresolvable_host_is_a_network_error(self) -> None:
        def failing(_: str) -> list[str]:
            raise OSError("NXDOMAIN")

        with pytest.raises(requests.exceptions.ConnectionError):
            validate_url("https://does-not-exist.example/", failing)

    def test_checks_ip_literals_without_dns(self) -> None:
        with pytest.raises(UnsafeUrlError):
            validate_url("http://169.254.169.254/latest/meta-data", resolver_for({}))
        with pytest.raises(UnsafeUrlError):
            validate_url("http://[::1]/", resolver_for({}))

    def test_accepts_public_https_url(self) -> None:
        validate_url("https://www.jobs.example.ch/stelle?id=1", resolver_for({}))


@dataclass
class FakeResponse:
    status_code: int = 200
    body: bytes = b"<html><title>Ok</title></html>"
    headers: dict[str, str] = field(default_factory=dict)
    encoding: str | None = "utf-8"
    apparent_encoding: str = "utf-8"

    @property
    def is_redirect(self) -> bool:
        return self.status_code in (301, 302, 303, 307, 308) and "Location" in self.headers

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(str(self.status_code))

    def iter_content(self, chunk_size: int) -> Iterator[bytes]:
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start : start + chunk_size]

    def close(self) -> None:
        pass


class FakeSession:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses
        self.requested: list[str] = []

    def get(self, url: str, **_: object) -> FakeResponse:
        self.requested.append(url)
        return self.responses[url]


class TestFetchPage:
    def test_returns_decoded_html(self) -> None:
        session = FakeSession({"https://a.ch/": FakeResponse(body="Läufer".encode())})
        page = fetch_page("https://a.ch/", session=session, resolver=resolver_for({}))  # type: ignore[arg-type]
        assert page.html == "Läufer"

    def test_follows_redirects_and_reports_final_url(self) -> None:
        session = FakeSession(
            {
                "https://a.ch/": FakeResponse(status_code=301, headers={"Location": "/job"}),
                "https://a.ch/job": FakeResponse(),
            }
        )
        page = fetch_page("https://a.ch/", session=session, resolver=resolver_for({}))  # type: ignore[arg-type]
        assert page.url == "https://a.ch/job"

    def test_revalidates_every_redirect_hop(self) -> None:
        """A public site must not be able to bounce the server to an internal address."""
        session = FakeSession(
            {
                "https://a.ch/": FakeResponse(
                    status_code=302, headers={"Location": "http://169.254.169.254/latest/meta-data"}
                ),
            }
        )
        with pytest.raises(UnsafeUrlError):
            fetch_page("https://a.ch/", session=session, resolver=resolver_for({}))  # type: ignore[arg-type]
        assert session.requested == ["https://a.ch/"]

    def test_stops_redirect_loops(self) -> None:
        loop = FakeResponse(status_code=302, headers={"Location": "https://a.ch/"})
        with pytest.raises(requests.exceptions.TooManyRedirects):
            fetch_page(
                "https://a.ch/",
                session=FakeSession({"https://a.ch/": loop}),
                resolver=resolver_for({}),
            )  # type: ignore[arg-type]

    def test_rejects_oversized_responses(self) -> None:
        huge = FakeResponse(body=b"x" * (MAX_BYTES + 1))
        with pytest.raises(requests.exceptions.ContentDecodingError):
            fetch_page(
                "https://a.ch/",
                session=FakeSession({"https://a.ch/": huge}),
                resolver=resolver_for({}),
            )  # type: ignore[arg-type]

    def test_http_errors_are_raised(self) -> None:
        missing = FakeResponse(status_code=404)
        with pytest.raises(requests.exceptions.HTTPError):
            fetch_page(
                "https://a.ch/",
                session=FakeSession({"https://a.ch/": missing}),
                resolver=resolver_for({}),
            )  # type: ignore[arg-type]
