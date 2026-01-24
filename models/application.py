from pydantic import BaseModel
from typing import Optional


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
