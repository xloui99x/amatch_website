"""Fetching user-supplied URLs without opening the server to SSRF.

The check endpoint downloads whatever URL a visitor types in. Without
safeguards an attacker could make the server request internal addresses
(``http://localhost:…``, ``http://169.254.169.254/`` cloud metadata, the
private network of the hosting provider) and read the response through the
report. This module prevents that:

- only ``http`` and ``https`` on the standard ports are allowed
- every hostname is resolved and *all* resulting IPs must be public
- redirects are followed manually, so each hop is validated again
- the body is streamed and capped, so a huge file cannot exhaust memory

DNS rebinding between our resolution and the connection is a remaining,
much narrower gap; closing it fully requires pinning the resolved IP in the
connection, which ``requests`` does not support without a custom adapter.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import requests

USER_AGENT = "Mozilla/5.0 (compatible; AMatchStellenanzeigenCheck/1.0; +https://amatch.ch)"
ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_PORTS = frozenset({None, 80, 443})
MAX_REDIRECTS = 5
MAX_BYTES = 3 * 1024 * 1024  # job ads are small; 3 MB is generous
TIMEOUT_SECONDS = 8

Resolver = Callable[[str], list[str]]


class UnsafeUrlError(ValueError):
    """The URL points somewhere the server must not connect to."""


@dataclass(frozen=True)
class FetchedPage:
    url: str
    """Final URL after redirects."""
    html: str


def resolve_host(host: str) -> list[str]:
    """Returns every IP address the hostname resolves to."""
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return sorted({str(info[4][0]) for info in infos})


def is_public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def validate_url(url: str, resolver: Resolver = resolve_host) -> None:
    """Raises UnsafeUrlError unless the URL is a public http(s) address."""
    parts = urlsplit(url)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"scheme not allowed: {parts.scheme!r}")
    if parts.username or parts.password:
        raise UnsafeUrlError("credentials in URL are not allowed")
    try:
        port = parts.port
    except ValueError as exc:
        raise UnsafeUrlError("invalid port") from exc
    if port not in ALLOWED_PORTS:
        raise UnsafeUrlError(f"port not allowed: {port}")

    host = parts.hostname
    if not host:
        raise UnsafeUrlError("missing host")

    try:
        # An IP literal is checked as-is; only hostnames go through DNS.
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        addresses = _resolve(host, resolver)
    if not addresses or not all(is_public_ip(address) for address in addresses):
        raise UnsafeUrlError(f"host resolves to a non-public address: {host}")


def _resolve(host: str, resolver: Resolver) -> list[str]:
    try:
        return resolver(host)
    except OSError as exc:
        raise requests.exceptions.ConnectionError(f"cannot resolve {host}") from exc


def fetch_page(
    url: str,
    *,
    session: requests.Session | None = None,
    resolver: Resolver = resolve_host,
) -> FetchedPage:
    """Downloads an HTML page from a public URL.

    Raises UnsafeUrlError for blocked targets and requests' exceptions for
    network problems.
    """
    http = session or requests.Session()
    current = url

    for _ in range(MAX_REDIRECTS + 1):
        validate_url(current, resolver)
        response = http.get(
            current,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
            allow_redirects=False,
            stream=True,
        )
        try:
            if response.is_redirect:
                location = response.headers.get("Location", "")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            body = _read_capped(response)
            # Let requests pick the charset from the headers, falling back to detection.
            encoding = response.encoding or response.apparent_encoding or "utf-8"
            return FetchedPage(url=current, html=body.decode(encoding, errors="replace"))
        finally:
            response.close()

    raise requests.exceptions.TooManyRedirects(f"more than {MAX_REDIRECTS} redirects")


def _read_capped(response: requests.Response) -> bytes:
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        size += len(chunk)
        if size > MAX_BYTES:
            raise requests.exceptions.ContentDecodingError("response too large")
        chunks.append(chunk)
    return b"".join(chunks)
