from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime

VALID_STATUSES = [
    "saved",
    "applied",
    "screening",
    "interviewing",
    "offer",
    "accepted",
    "rejected",
    "withdrawn",
]


class ApplicationCreate(BaseModel):
    job_title: str
    company: str
    location: Optional[str] = None
    job_url: Optional[str] = None
    job_description: Optional[str] = None
    status: Optional[str] = "applied"
    deadline: Optional[str] = None
    follow_up_date: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v and v not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{v}'. Must be one of: {', '.join(VALID_STATUSES)}")
        return v


class ApplicationUpdate(BaseModel):
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    job_url: Optional[str] = None
    job_description: Optional[str] = None
    status: Optional[str] = None
    deadline: Optional[str] = None
    follow_up_date: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v and v not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{v}'. Must be one of: {', '.join(VALID_STATUSES)}")
        return v


class StatusHistoryEntry(BaseModel):
    id: int
    from_status: Optional[str]
    to_status: str
    notes: Optional[str]
    changed_at: datetime


class Application(BaseModel):
    id: int
    job_title: str
    company: str
    location: Optional[str]
    job_url: Optional[str]
    job_description: Optional[str]
    status: str
    applied_date: str
    deadline: Optional[str]
    follow_up_date: Optional[str]
    notes: Optional[str]
    created_at: str
    updated_at: str
