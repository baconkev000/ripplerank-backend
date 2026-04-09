"""Host/domain normalization without importing Django models (avoids circular imports)."""

from __future__ import annotations

from urllib.parse import urlparse


def normalize_tracked_competitor_domain(raw: str) -> str | None:
    """
    Normalize user input to a single base host for competitor tracking.

    - Strips paths, query strings, and fragments
    - Lowercases; strips leading www.
    - Drops :80 and :443 ports
    - Accepts full URL or bare hostname (with optional path, which is ignored)
    """
    v = (raw or "").strip()
    if not v:
        return None
    if not v.startswith(("http://", "https://")):
        v = "https://" + v
    parsed = urlparse(v)
    host = (parsed.netloc or "").strip().lower()
    if not host and parsed.path:
        first = (parsed.path or "").lstrip("/").split("/")[0]
        if first and "." in first and " " not in first and ".." not in first:
            host = first.lower()
    if not host:
        return None
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    if ":" in host:
        h, _, port_s = host.rpartition(":")
        if port_s.isdigit():
            p = int(port_s)
            if p in (80, 443):
                host = h
    if host.startswith("www."):
        host = host[4:]
    if not host or "/" in host or ".." in host or " " in host:
        return None
    return host
