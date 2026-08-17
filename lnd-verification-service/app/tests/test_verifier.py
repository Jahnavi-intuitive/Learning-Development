"""
Tests the decision logic in verifier.py without making any real network
calls -- fetch_public_badge is monkeypatched so these run offline, every
time, in any environment (exactly what you want in CI later).
"""
import pytest

from app.models import CertificateRecord, Verification, VerificationStatus, CertStatus
from app.services.credly import CredlyBadgeData, CredlyFetchError
from app.services import verifier as verifier_module


@pytest.mark.asyncio
async def test_matching_name_and_cert_verifies(db_session, sample_employee, monkeypatch):
    async def fake_fetch(url):
        return CredlyBadgeData(recipient_name="Jahnavi Patel", badge_name="AWS Certified Cloud Practitioner")

    monkeypatch.setattr(verifier_module, "fetch_public_badge", fake_fetch)

    result = await verifier_module.run_verification(
        db_session, sample_employee, "AWS Certified Cloud Practitioner", "https://www.credly.com/badges/fake/public_url"
    )

    assert result.status == VerificationStatus.verified
    assert result.certificate_record.status == CertStatus.verified


@pytest.mark.asyncio
async def test_name_mismatch_goes_to_exception_queue(db_session, sample_employee, monkeypatch):
    async def fake_fetch(url):
        return CredlyBadgeData(recipient_name="Someone Else Entirely", badge_name="AWS Certified Cloud Practitioner")

    monkeypatch.setattr(verifier_module, "fetch_public_badge", fake_fetch)

    result = await verifier_module.run_verification(
        db_session, sample_employee, "AWS Certified Cloud Practitioner", "https://www.credly.com/badges/fake/public_url"
    )

    # Never "rejected" -- always routed to the human exception queue (FR-3.4).
    assert result.status == VerificationStatus.needs_review


@pytest.mark.asyncio
async def test_unreachable_proof_url_goes_to_exception_queue(db_session, sample_employee, monkeypatch):
    async def fake_fetch(url):
        raise CredlyFetchError("404 Not Found")

    monkeypatch.setattr(verifier_module, "fetch_public_badge", fake_fetch)

    result = await verifier_module.run_verification(
        db_session, sample_employee, "AWS Certified Cloud Practitioner", "https://www.credly.com/badges/does-not-exist/public_url"
    )

    assert result.status == VerificationStatus.needs_review
    assert "could not confirm" in result.notes.lower()


@pytest.mark.asyncio
async def test_reverifying_same_cert_reuses_the_record(db_session, sample_employee, monkeypatch):
    async def fake_fetch(url):
        raise CredlyFetchError("404 Not Found")

    monkeypatch.setattr(verifier_module, "fetch_public_badge", fake_fetch)

    first = await verifier_module.run_verification(
        db_session, sample_employee, "AWS Certified Cloud Practitioner", "https://www.credly.com/badges/fake/public_url"
    )
    second = await verifier_module.run_verification(
        db_session, sample_employee, "AWS Certified Cloud Practitioner", "https://www.credly.com/badges/fake/public_url"
    )

    # Same certificate record reused across attempts -- no duplicate record.
    assert first.certificate_record_id == second.certificate_record_id
    assert db_session.query(CertificateRecord).count() == 1
    # Each attempt still gets its own Verification row for the audit trail.
    assert db_session.query(Verification).count() == 2
