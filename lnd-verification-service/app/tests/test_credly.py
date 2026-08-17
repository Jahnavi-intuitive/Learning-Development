"""
Tests the Credly badge-page parser against real page shapes (FR-3.2).
Uses respx to mock the HTTP layer so these run offline.
"""
import pytest
import respx
import httpx

from app.services.credly import fetch_public_badge, CredlyFetchError

BADGE_URL = "https://www.credly.com/badges/ed6d5cdb-2770-4589-8148-cbbcf9b04e36/public_url"


def _page(og_title: str) -> str:
    return f"""
    <html><head>
    <meta property="og:title" content="{og_title}">
    </head><body></body></html>
    """


@pytest.mark.asyncio
async def test_parses_real_credly_issued_to_format():
    # This is the actual og:title format Credly serves today, confirmed
    # against a live badge page -- not the "<Name> earned <Badge>" shape
    # this parser used to assume.
    html = _page(
        "Claude Certified Architect - Foundations was issued by Anthropic to Jahnavi Patel."
    )
    with respx.mock:
        respx.get(BADGE_URL).mock(return_value=httpx.Response(200, text=html))
        badge = await fetch_public_badge(BADGE_URL)

    assert badge.recipient_name == "Jahnavi Patel"
    assert badge.badge_name == "Claude Certified Architect - Foundations"
    assert badge.raw_source == "og:title"


@pytest.mark.asyncio
async def test_parses_legacy_earned_format():
    html = _page("Jahnavi Patel earned AWS Certified Cloud Practitioner.")
    with respx.mock:
        respx.get(BADGE_URL).mock(return_value=httpx.Response(200, text=html))
        badge = await fetch_public_badge(BADGE_URL)

    assert badge.recipient_name == "Jahnavi Patel"
    assert badge.badge_name == "AWS Certified Cloud Practitioner"


@pytest.mark.asyncio
async def test_unparseable_page_raises_credly_fetch_error():
    html = "<html><head><title>Nothing useful here</title></head><body></body></html>"
    with respx.mock:
        respx.get(BADGE_URL).mock(return_value=httpx.Response(200, text=html))
        with pytest.raises(CredlyFetchError):
            await fetch_public_badge(BADGE_URL)
