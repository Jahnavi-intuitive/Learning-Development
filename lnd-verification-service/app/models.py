"""
SQLAlchemy models for the slice of the BRD's data model (Section 10.1) that
this workflow (Phase 3 - Certificate Upload & Automated Verification) needs:
Employee, Certificate Record, Verification, Audit Log.

Catalog, Learning Path, Knowledge Item, Escalation, and Notification belong
to other workflows/phases and aren't modeled here yet.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Enum, Text
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class CertStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"      # employee says they finished it, not yet verified
    verified = "verified"        # auto-verification confirmed it
    needs_review = "needs_review"  # auto-verification couldn't confirm -> exception queue
    expiring = "expiring"


class VerificationStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    needs_review = "needs_review"
    # Deliberately no "rejected"/"failed" auto-status: FR-3.4 requires routing
    # failed auto-verification to a human exception queue, never auto-rejecting.


class VerificationMethod(str, enum.Enum):
    public_link_crosscheck = "public_link_crosscheck"
    document_scan = "document_scan"
    manual = "manual"  # L&D admin resolved it by hand from the exception queue


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)

    certificate_records = relationship("CertificateRecord", back_populates="employee")


class CertificateRecord(Base):
    __tablename__ = "certificate_records"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    certification_name = Column(String, nullable=False)
    status = Column(Enum(CertStatus), default=CertStatus.completed, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    employee = relationship("Employee", back_populates="certificate_records")
    verifications = relationship("Verification", back_populates="certificate_record")


class Verification(Base):
    __tablename__ = "verifications"

    id = Column(Integer, primary_key=True, index=True)
    certificate_record_id = Column(Integer, ForeignKey("certificate_records.id"), nullable=False)
    status = Column(Enum(VerificationStatus), default=VerificationStatus.pending, nullable=False)
    method = Column(Enum(VerificationMethod), nullable=False)
    proof_url = Column(String, nullable=True)
    verifier = Column(String, default="system")  # "system" or an L&D admin's identifier
    notes = Column(Text, nullable=True)           # why it landed in needs_review, match scores, etc.
    created_at = Column(DateTime, default=utcnow)

    certificate_record = relationship("CertificateRecord", back_populates="verifications")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String, nullable=False)         # "system" or an admin identifier
    action = Column(String, nullable=False)        # e.g. "verification_attempt", "exception_resolved"
    entity_type = Column(String, nullable=False)   # "certificate_record" | "verification"
    entity_id = Column(Integer, nullable=False)
    before_state = Column(Text, nullable=True)
    after_state = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=utcnow)
