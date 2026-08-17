from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class EmployeeCreate(BaseModel):
    name: str
    email: EmailStr


class EmployeeOut(BaseModel):
    id: int
    name: str
    email: str
    model_config = {"from_attributes": True}


class VerifyRequest(BaseModel):
    employee_id: int
    certification_name: str
    proof_url: str  # public credential link, e.g. a Credly badge URL


class VerificationOut(BaseModel):
    id: int
    certificate_record_id: int
    status: str
    method: str
    proof_url: Optional[str]
    verifier: str
    notes: Optional[str]
    model_config = {"from_attributes": True}


class VerificationDetailOut(VerificationOut):
    """Same as VerificationOut, plus the employee/cert context the UI needs
    so it doesn't have to make a second round-trip per row."""
    created_at: datetime
    employee_name: str
    employee_email: str
    certification_name: str
    certificate_status: str


class ExceptionResolution(BaseModel):
    approve: bool
    resolved_by: str
    notes: Optional[str] = None


class StatsOut(BaseModel):
    total_employees: int
    total_certificate_records: int
    verified: int
    needs_review: int
    pending: int
