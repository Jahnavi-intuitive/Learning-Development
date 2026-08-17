"""
Orchestrates one verification attempt end to end (FR-3.1-3.4):
  1. fetch the public credential page
  2. run the name-match guardrail
  3. check the badge name roughly matches the claimed certification
  4. decide: verified, or needs_review (exception queue) -- never "rejected"
  5. write the Verification + update the CertificateRecord + write an
     AuditLog row, all in one place so nothing forgets the audit trail.
"""
import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    CertificateRecord, CertStatus, Verification, VerificationStatus,
    VerificationMethod, AuditLog, Employee,
)
from app.services.credly import fetch_public_badge, CredlyFetchError
from app.services.name_match import match_score
from app.config import settings


async def run_verification(
    db: Session, employee: Employee, certification_name: str, proof_url: str
) -> Verification:
    # 1. Reuse the certificate record for this employee + certification if
    # one already exists, rather than creating a new one on every attempt --
    # otherwise re-verifying (e.g. after fixing a bad proof URL) leaves a
    # duplicate record behind, and duplicate rows in the exception queue.
    record = (
        db.query(CertificateRecord)
        .filter(
            CertificateRecord.employee_id == employee.id,
            func.lower(CertificateRecord.certification_name) == certification_name.strip().lower(),
        )
        .first()
    )
    if record is None:
        record = CertificateRecord(
            employee_id=employee.id,
            certification_name=certification_name,
            status=CertStatus.completed,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

    before = {"status": record.status.value}

    # 2. Attempt the public-link cross-check.
    try:
        badge = await fetch_public_badge(proof_url)
    except CredlyFetchError as exc:
        verification = _save_verification(
            db, record, VerificationStatus.needs_review,
            VerificationMethod.public_link_crosscheck, proof_url,
            notes=f"Auto-verification could not confirm this credential: {exc}",
        )
        record.status = CertStatus.needs_review
        db.commit()
        _write_audit(db, record, before, "verification_attempt")
        return verification

    # 3. Name-match guardrail + rough certification-name check.
    name_similarity = match_score(employee.name, badge.recipient_name)
    cert_similarity = match_score(certification_name, badge.badge_name)
    name_ok = name_similarity >= settings.name_match_threshold
    cert_ok = cert_similarity >= 0.5  # looser: cert titles vary in phrasing across providers

    if name_ok and cert_ok:
        status = VerificationStatus.verified
        record.status = CertStatus.verified
        notes = (
            f"Verified via {badge.raw_source}. "
            f"name_similarity={name_similarity:.2f}, cert_similarity={cert_similarity:.2f}."
        )
    else:
        status = VerificationStatus.needs_review
        record.status = CertStatus.needs_review
        notes = (
            f"Auto-verification inconclusive -- routed to exception queue. "
            f"name_similarity={name_similarity:.2f} (need >= {settings.name_match_threshold}), "
            f"cert_similarity={cert_similarity:.2f}. "
            f"Page said recipient='{badge.recipient_name}', badge='{badge.badge_name}'."
        )

    verification = _save_verification(
        db, record, status, VerificationMethod.public_link_crosscheck, proof_url, notes
    )
    db.commit()
    _write_audit(db, record, before, "verification_attempt")
    return verification


def resolve_exception(db: Session, verification: Verification, approve: bool, resolved_by: str, notes: str | None):
    """An L&D admin resolving an item from the exception queue (FR-3.4)."""
    record = verification.certificate_record
    before = {"status": record.status.value}

    verification.status = VerificationStatus.verified if approve else VerificationStatus.needs_review
    verification.method = VerificationMethod.manual
    verification.verifier = resolved_by
    verification.notes = (verification.notes or "") + f"\n[manual resolution by {resolved_by}] {notes or ''}"

    record.status = CertStatus.verified if approve else CertStatus.needs_review
    db.commit()
    db.refresh(verification)

    _write_audit(db, record, before, "exception_resolved", actor=resolved_by)
    return verification


def _save_verification(db, record, status, method, proof_url, notes):
    verification = Verification(
        certificate_record_id=record.id,
        status=status,
        method=method,
        proof_url=proof_url,
        verifier="system",
        notes=notes,
    )
    db.add(verification)
    db.commit()
    db.refresh(verification)
    return verification


def _write_audit(db, record, before, action, actor="system"):
    log = AuditLog(
        actor=actor,
        action=action,
        entity_type="certificate_record",
        entity_id=record.id,
        before_state=json.dumps(before),
        after_state=json.dumps({"status": record.status.value}),
    )
    db.add(log)
    db.commit()
