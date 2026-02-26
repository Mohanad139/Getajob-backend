from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from .auth import User


class WorkExperienceCreate(BaseModel):
    company: str
    title: str
    start_date: date
    end_date: Optional[date] = None
    is_current: bool = False
    responsibilities: Optional[str] = None


class WorkExperienceUpdate(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None
    responsibilities: Optional[str] = None


class WorkExperience(BaseModel):
    id: int
    user_id: int
    company: str
    title: str
    start_date: date
    end_date: Optional[date]
    is_current: bool
    responsibilities: Optional[str]
    created_at: str


class EducationCreate(BaseModel):
    school: str
    degree: str
    field_of_study: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    gpa: Optional[str] = None


class EducationUpdate(BaseModel):
    school: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    gpa: Optional[str] = None


class Education(BaseModel):
    id: int
    user_id: int
    school: str
    degree: str
    field_of_study: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    gpa: Optional[str]
    created_at: str


class SkillCreate(BaseModel):
    skill_name: str
    proficiency: Optional[str] = None


class SkillUpdate(BaseModel):
    skill_name: Optional[str] = None
    proficiency: Optional[str] = None


class Skill(BaseModel):
    id: int
    user_id: int
    skill_name: str
    proficiency: Optional[str]
    created_at: str


class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None
    technologies: Optional[str] = None
    url: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    technologies: Optional[str] = None
    url: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class Project(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str]
    technologies: Optional[str]
    url: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    created_at: str


class CompleteResume(BaseModel):
    user: User
    work_experiences: List[WorkExperience]
    education: List[Education]
    skills: List[Skill]
    projects: List[Project]


class ResumeAnalysisRequest(BaseModel):
    job_description: str


class ResumeAnalysisResponse(BaseModel):
    match_score: int
    strengths: List[str]
    gaps: List[str]
    suggestions: List[str]
    keywords_to_add: List[str]


class TailoredResumeRequest(BaseModel):
    job_title: str
    job_description: str


class ResumeUploadResponse(BaseModel):
    message: str
    filename: str
    file_size: int
    parsed_data: dict
    counts: dict
