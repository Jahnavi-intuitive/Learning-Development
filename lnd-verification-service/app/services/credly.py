"""
Public-link cross-check against a Credly badge page (FR-3.2).

Credly badge public pages (https://www.credly.com/badges/<uuid>/public_url)
are a client-rendered React app -- the recipient/badge data is fetched by
the browser after load, not present in the initial HTML. The one thing
Credly does render server-side (for link previews/SEO) is the og:title
meta tag, confirmed against a live badge page:

    <meta property="og:title" content="<Badge Name> was issued by <Issuer> to <Recipient Name>.">

This parser tries that pattern first, then a couple of other shapes
(JSON-LD, an "<Name> earned <Badge>" og:title variant) in case Credly
changes templates again or this ever sees another Open Badges provider,
and raises a clear error if none match rather than guessing.

IMPORTANT: Credly's markup can change without notice. If auto-verification
starts failing again, view-source a real badge page and check this module's
selectors still match.
"""
import json
import re
import ssl
from dataclasses import dataclass

import certifi
import httpx
from bs4 import BeautifulSoup

from app.config import settings

_ISSUED_TO_RE = re.compile(
    r"^(?P<badge>.+?)\s+was issued by\s+.+?\s+to\s+(?P<recipient>.+?)\.?\s*$"
)

# Built once at import time and reused across requests. Building a fresh
# SSLContext from the certifi bundle on every call (the default behavior of
# a plain `httpx.AsyncClient()`) can take 15+ seconds on some machines
# (observed on Windows, likely AV real-time scanning of the cert bundle on
# each read) -- turning every /verify call into a multi-second wait.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class CredlyFetchError(Exception):
    """Raised when the badge page can't be fetched or parsed. Callers should
    treat this as "send to the exception queue", never as "reject"."""


@dataclass
class CredlyBadgeData:
    recipient_name: str
    badge_name: str
    issued_date: str | None = None
    raw_source: str = ""  # which parsing strategy found the data, for audit notes


async def fetch_public_badge(url: str) -> CredlyBadgeData:
    try:
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds, verify=_SSL_CONTEXT
        ) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise CredlyFetchError(f"Could not reach proof URL: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")

    # Strategy 1: JSON-LD structured data, if Credly includes it.
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        name = _dig(data, ["recipient", "name"]) or _dig(data, ["awardedTo", "name"])
        badge = data.get("name")
        if name and badge:
            return CredlyBadgeData(recipient_name=name, badge_name=badge, raw_source="json-ld")

    # Strategy 2: og:title meta tag, "<Badge Name> was issued by <Issuer> to
    # <Recipient Name>." -- this is Credly's current real-world template.
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        content = og_title["content"].strip()

        issued_match = _ISSUED_TO_RE.match(content)
        if issued_match:
            return CredlyBadgeData(
                recipient_name=issued_match.group("recipient").strip(),
                badge_name=issued_match.group("badge").strip(),
                raw_source="og:title",
            )

        # Strategy 3: older/alternate template, "<Name> earned <Badge Name>".
        if " earned " in content:
            name_part, badge_part = content.split(" earned ", 1)
            return CredlyBadgeData(
                recipient_name=name_part.strip(),
                badge_name=badge_part.strip().rstrip("."),
                raw_source="og:title",
            )

    raise CredlyFetchError(
        "Recognized page but couldn't locate recipient/badge data with the "
        "current selectors -- inspect the page and update app/services/credly.py."
    )


def _dig(data: dict, path: list[str]):
    cur = data
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur
