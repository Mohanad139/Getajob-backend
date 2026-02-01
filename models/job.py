from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class JobSearchRequest(BaseModel):
    query: str
    location: Optional[str] = ""
    max_jobs: Optional[int] = 100  # Fetch up to 100 jobs by default
    date_posted: Optional[str] = "week"  # Options: "all", "today", "3days", "week", "month"
    sort_by: Optional[str] = "date"  # Options: "relevance", "date"
    refresh: Optional[bool] = False  # Bypass cache for fresh results


class JobSearchResponse(BaseModel):
    message: str
    jobs_fetched: int
    jobs_saved: int


class Job(BaseModel):
    id: int
    job_id: str
    title: str
    company: str
    location: Optional[str]
    salary: Optional[str]
    job_type: Optional[str]
    description: Optional[str]
    url: str
    source: str
    posted_date: Optional[datetime]
    scraped_at: datetime


class JobSave(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    salary: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    job_type: Optional[str] = None
    posted_date: Optional[str] = None


class JobSkip(BaseModel):
    title: str
    company: str
    location: Optional[str] = None


class SkippedJob(BaseModel):
    id: int
    title: str
    company: str
    location: Optional[str]
    skipped_at: datetime
