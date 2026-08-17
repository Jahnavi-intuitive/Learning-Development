from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee, CertificateRecord, Verification, VerificationStatus, CertStatus
from app.schemas import (
    EmployeeCreate, EmployeeOut, VerifyRequest, VerificationOut, VerificationDetailOut,
    ExceptionResolution, StatsOut,
)
from app.services.verifier import run_verification, resolve_exception

router = APIRouter()


def _to_detail(v: Verification) -> VerificationDetailOut:
    record = v.certificate_record
    return VerificationDetailOut(
        id=v.id,
        certificate_record_id=v.certificate_record_id,
        status=v.status.value if hasattr(v.status, "value") else v.status,
        method=v.method.value if hasattr(v.method, "value") else v.method,
        proof_url=v.proof_url,
        verifier=v.verifier,
        notes=v.notes,
        created_at=v.created_at,
        employee_name=record.employee.name,
        employee_email=record.employee.email,
        certification_name=record.certification_name,
        certificate_status=record.status.value if hasattr(record.status, "value") else record.status,
    )


# --- Employees (minimal, just enough to exercise verification end to end) ---
# In the real system this comes from HRIS/corporate directory (BRD Section 11),
# not from a POST endpoint -- this exists purely so you can test locally
# without a directory integration in place yet.

@router.post("/employees", response_model=EmployeeOut)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db)):
    employee = Employee(name=payload.name, email=payload.email)
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees(db: Session = Depends(get_db)):
    return db.query(Employee).order_by(Employee.id.asc()).all()


@router.get("/employees/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


# --- Verification (FR-3.1 - FR-3.4) ---

@router.post("/verify", response_model=VerificationDetailOut)
async def verify_certificate(payload: VerifyRequest, db: Session = Depends(get_db)):
    employee = db.get(Employee, payload.employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    verification = await run_verification(
        db, employee, payload.certification_name, payload.proof_url
    )
    return _to_detail(verification)


@router.get("/verifications/{verification_id}", response_model=VerificationDetailOut)
def get_verification(verification_id: int, db: Session = Depends(get_db)):
    verification = db.get(Verification, verification_id)
    if not verification:
        raise HTTPException(status_code=404, detail="Verification not found")
    return _to_detail(verification)


@router.get("/exceptions", response_model=list[VerificationDetailOut])
def list_exceptions(db: Session = Depends(get_db)):
    """The L&D admin exception queue (FR-3.4): the most recent verification
    attempt for each certificate record, where that attempt still needs
    review. Re-verifying a record (e.g. after fixing a bad proof URL) adds a
    new Verification row for the audit trail, but only its latest attempt
    should show up here -- otherwise superseded attempts pile up as
    duplicate queue rows for what's really one certificate."""
    latest_ids = (
        db.query(func.max(Verification.id))
        .group_by(Verification.certificate_record_id)
        .subquery()
    )
    rows = (
        db.query(Verification)
        .filter(Verification.id.in_(latest_ids))
        .filter(Verification.status == VerificationStatus.needs_review)
        .order_by(Verification.created_at.asc())
        .all()
    )
    return [_to_detail(v) for v in rows]


@router.post("/exceptions/{verification_id}/resolve", response_model=VerificationDetailOut)
def resolve_exception_endpoint(
    verification_id: int, payload: ExceptionResolution, db: Session = Depends(get_db)
):
    verification = db.get(Verification, verification_id)
    if not verification:
        raise HTTPException(status_code=404, detail="Verification not found")
    resolved = resolve_exception(db, verification, payload.approve, payload.resolved_by, payload.notes)
    return _to_detail(resolved)


# --- Stats (powers the stat tiles in the local admin UI, static/index.html) ---

@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    return StatsOut(
        total_employees=db.query(Employee).count(),
        total_certificate_records=db.query(CertificateRecord).count(),
        verified=db.query(CertificateRecord).filter(CertificateRecord.status == CertStatus.verified).count(),
        needs_review=db.query(CertificateRecord).filter(CertificateRecord.status == CertStatus.needs_review).count(),
        pending=db.query(CertificateRecord).filter(CertificateRecord.status == CertStatus.completed).count(),
    )
