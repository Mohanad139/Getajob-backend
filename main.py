from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, date, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from database import get_connection
from scraper import fetch_jobs, save_jobs_to_db
import os
import json
from dotenv import load_dotenv
import jwt
import bcrypt
from fastapi.responses import StreamingResponse
from resume_generator import generate_resume, generate_tailored_resume
from resume_ai import get_user_resume_data, analyze_resume_match, tailor_resume
from interview_ai import generate_interview_questions, evaluate_answer, get_overall_feedback


# Load environment variables
load_dotenv()

# JWT Settings
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

app = FastAPI(title="Interview AI API")

# Security scheme
security = HTTPBearer()

# Enable CORS for your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ AUTH MODELS ============

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    location: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None

class User(BaseModel):
    id: int
    email: str
    name: str
    phone: Optional[str]
    location: Optional[str]
    headline: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime

class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None

# ============ AUTH HELPER FUNCTIONS ============

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id: int = payload.get("user_id")
        email: str = payload.get("email")
        if user_id is None:
            return None
        return TokenData(user_id=user_id, email=email)
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    token_data = decode_access_token(token)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT id, email, name, phone, location, created_at FROM users WHERE id = %s", (token_data.user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user

# ============ WORK EXPERIENCE MODELS ============

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

# ============ EDUCATION MODELS ============

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

# ============ SKILLS MODELS ============

class SkillCreate(BaseModel):
    skill_name: str
    proficiency: Optional[str] = None  # beginner, intermediate, advanced, expert

class SkillUpdate(BaseModel):
    skill_name: Optional[str] = None
    proficiency: Optional[str] = None

class Skill(BaseModel):
    id: int
    user_id: int
    skill_name: str
    proficiency: Optional[str]
    created_at: str

# ============ PROJECTS MODELS ============

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

# ============ COMPLETE RESUME MODEL ============

class CompleteResume(BaseModel):
    user: User
    work_experiences: List[WorkExperience]
    education: List[Education]
    skills: List[Skill]
    projects: List[Project]

# ============ Resume rephrase ============


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


# Request models
class JobSearchRequest(BaseModel):
    query: str
    location: Optional[str] = ""
    num_pages: Optional[int] = 1

class JobSearchResponse(BaseModel):
    message: str
    jobs_fetched: int
    jobs_saved: int

# Response models
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

class ApplicationCreate(BaseModel):
    job_title: str
    company: str
    location: Optional[str] = None
    job_url: Optional[str] = None
    job_description: Optional[str] = None
    status: Optional[str] = "applied"
    deadline: Optional[str] = None  # ISO format: "2026-01-25T10:00:00"
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



# ============ Interview session ============

class InterviewSessionCreate(BaseModel):
    job_title: str
    job_description: str
    num_questions: Optional[int] = 5

class InterviewQuestionResponse(BaseModel):
    id: int
    question_type: str
    question_text: str
    user_answer: Optional[str]
    ai_feedback: Optional[str]
    score: Optional[int]

class AnswerSubmit(BaseModel):
    question_id: int
    answer: str

class InterviewFeedback(BaseModel):
    score: int
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]



@app.get("/")
def read_root():
    return {"message": "Welcome to Interview AI API"}

# ============ AUTH ENDPOINTS ============

@app.post("/api/auth/register", response_model=dict)
async def register(user: UserCreate):
    """Register a new user"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (user.email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Email already registered")

        # Hash password and create user
        hashed_password = hash_password(user.password)
        cursor.execute("""
            INSERT INTO users (email, password_hash, name, phone, location)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, email, name, phone, location
        """, (user.email, hashed_password, user.name, user.phone, user.location))

        new_user = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        # Create access token
        access_token = create_access_token(
            data={"user_id": new_user['id'], "email": new_user['email']}
        )

        return {
            "message": "User registered successfully",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": new_user['id'],
                "email": new_user['email'],
                "name": new_user['name'],
                "phone": new_user['phone'],
                "location": new_user['location']
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/login", response_model=dict)
async def login(credentials: UserLogin):
    """Login and get access token"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Find user by email
        cursor.execute(
            "SELECT id, email, password_hash, name, phone, location FROM users WHERE email = %s",
            (credentials.email,)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or not verify_password(credentials.password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        # Create access token
        access_token = create_access_token(
            data={"user_id": user['id'], "email": user['email']}
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user['id'],
                "email": user['email'],
                "name": user['name'],
                "phone": user['phone'],
                "location": user['location']
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auth/me", response_model=dict)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    return {
        "id": current_user['id'],
        "email": current_user['email'],
        "name": current_user['name'],
        "phone": current_user.get('phone'),
        "location": current_user.get('location'),
        "headline": current_user.get('headline'),
        "summary": current_user.get('summary')
    }

@app.put("/api/auth/profile", response_model=dict)
async def update_profile(update_data: UserUpdate, current_user: dict = Depends(get_current_user)):
    """Update current user's profile"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Build dynamic update query
        update_fields = []
        params = []

        if update_data.name is not None:
            update_fields.append("name = %s")
            params.append(update_data.name)
        if update_data.phone is not None:
            update_fields.append("phone = %s")
            params.append(update_data.phone)
        if update_data.location is not None:
            update_fields.append("location = %s")
            params.append(update_data.location)
        if update_data.headline is not None:
            update_fields.append("headline = %s")
            params.append(update_data.headline)
        if update_data.summary is not None:
            update_fields.append("summary = %s")
            params.append(update_data.summary)

        if not update_fields:
            return {"message": "No fields to update"}

        params.append(current_user['id'])

        query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s RETURNING *"
        cursor.execute(query, params)
        updated_user = cursor.fetchone()

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "message": "Profile updated successfully",
            "user": {
                "id": updated_user['id'],
                "email": updated_user['email'],
                "name": updated_user['name'],
                "phone": updated_user.get('phone'),
                "location": updated_user.get('location'),
                "headline": updated_user.get('headline'),
                "summary": updated_user.get('summary')
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ JOB ENDPOINTS ============

class JobSave(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    salary: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    job_type: Optional[str] = None
    posted_date: Optional[str] = None

@app.post("/api/jobs/search", response_model=dict)
async def search_jobs(request: JobSearchRequest):
    """
    Endpoint to search and fetch jobs from JSearch API
    Returns the jobs directly for display (does NOT auto-save)
    Query should include location, e.g. "Software Engineer in Canada"
    """
    try:
        # Fetch jobs from API - query should include location
        raw_jobs = fetch_jobs(
            query=request.query,
            location="",
            num_pages=request.num_pages
        )

        if not raw_jobs:
            return {"jobs": [], "message": "No jobs found"}

        # Transform jobs to a simpler format for the frontend
        jobs = []
        for job in raw_jobs:
            # Format salary as string
            salary_min = job.get('job_min_salary')
            salary_max = job.get('job_max_salary')
            if salary_min and salary_max:
                salary = f"${salary_min:,} - ${salary_max:,}"
            elif salary_min:
                salary = f"${salary_min:,}"
            elif salary_max:
                salary = f"${salary_max:,}"
            else:
                salary = None

            # Build location string with city, state, and country
            city = job.get('job_city', '') or ''
            state = job.get('job_state', '') or ''
            country = job.get('job_country', '') or ''
            location_parts = [p for p in [city, state, country] if p]
            job_location = ', '.join(location_parts) if location_parts else ''

            jobs.append({
                "title": job.get('job_title', '') or '',
                "company": job.get('employer_name', '') or '',
                "location": job_location,
                "salary": salary,
                "description": (job.get('job_description', '') or '')[:500],
                "url": job.get('job_apply_link', '') or job.get('job_google_link', '') or '',
                "job_type": job.get('job_employment_type', '') or '',
                "posted_date": job.get('job_posted_at_datetime_utc', '') or ''
            })

        # Jobs are NOT auto-saved - user must explicitly save
        return {"jobs": jobs, "message": f"Found {len(jobs)} jobs"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/jobs", response_model=dict)
async def save_job(job: JobSave, current_user: dict = Depends(get_current_user)):
    """
    Save a job to the database for the current user (requires authentication)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Generate a unique job_id
        import uuid
        job_id = str(uuid.uuid4())[:20]

        cursor.execute("""
            INSERT INTO jobs (job_id, title, company, location, salary, job_type, description, url, posted_date, source, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            job_id,
            job.title,
            job.company,
            job.location,
            job.salary,
            job.job_type,
            job.description,
            job.url,
            job.posted_date if job.posted_date else None,
            'user_saved',
            current_user['id']
        ))

        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Job saved successfully", "id": result['id']}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: int, current_user: dict = Depends(get_current_user)):
    """
    Delete a job from the database (requires authentication, must be owner)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Only delete if the job belongs to the current user
        cursor.execute("DELETE FROM jobs WHERE id = %s AND user_id = %s RETURNING id", (job_id, current_user['id']))
        result = cursor.fetchone()

        if not result:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Job not found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Job deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs", response_model=List[Job])
async def get_jobs(
    company: Optional[str] = None,
    location: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Endpoint to get current user's saved jobs with optional filters (requires authentication)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Build query with filters - only get current user's jobs
        query = "SELECT * FROM jobs WHERE user_id = %s"
        params = [current_user['id']]

        if company:
            query += " AND company ILIKE %s"
            params.append(f"%{company}%")

        if location:
            query += " AND location ILIKE %s"
            params.append(f"{location}%")

        # Order by most recently added (id DESC) so newly saved jobs appear first
        query += " ORDER BY id DESC"

        cursor.execute(query, params)
        jobs = cursor.fetchall()

        cursor.close()
        conn.close()

        return jobs

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """
    Get a specific job by id (numeric) or job_id (string)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Try to match by numeric id first, then by job_id string
        if job_id.isdigit():
            cursor.execute("SELECT * FROM jobs WHERE id = %s OR job_id = %s", (int(job_id), job_id))
        else:
            cursor.execute("SELECT * FROM jobs WHERE job_id = %s", (job_id,))

        job = cursor.fetchone()

        cursor.close()
        conn.close()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return job

    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats():
    """
    Get database statistics
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_jobs,
                COUNT(DISTINCT company) as total_companies,
                COUNT(DISTINCT location) as total_locations
            FROM jobs
            WHERE is_active = TRUE
        """)
        stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/applications", response_model=dict)
async def create_application(application: ApplicationCreate, current_user: dict = Depends(get_current_user)):
    """
    Create a new job application with job details (requires authentication)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Insert application with job details directly
        cursor.execute("""
            INSERT INTO applications (user_id, job_title, company, location, job_url, job_description, status, deadline, follow_up_date, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            current_user['id'],
            application.job_title,
            application.company,
            application.location,
            application.job_url,
            application.job_description,
            application.status,
            application.deadline,
            application.follow_up_date,
            application.notes
        ))

        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Application created successfully", "id": result['id']}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/applications", response_model=List[dict])
async def get_applications(
    status: Optional[str] = None,
    upcoming_deadlines: Optional[bool] = False,
    current_user: dict = Depends(get_current_user)
):
    """
    Get current user's applications with optional filters (requires authentication)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT * FROM applications
            WHERE user_id = %s
        """
        params = [current_user['id']]

        if status:
            query += " AND status = %s"
            params.append(status)

        if upcoming_deadlines:
            query += " AND deadline IS NOT NULL AND deadline > NOW()"
            query += " ORDER BY deadline ASC"
        else:
            query += " ORDER BY applied_date DESC"

        cursor.execute(query, params)
        applications = cursor.fetchall()

        cursor.close()
        conn.close()

        return applications

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/applications/{application_id}")
async def get_application(application_id: int, current_user: dict = Depends(get_current_user)):
    """
    Get a specific application (requires authentication, must be owner)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT * FROM applications
            WHERE id = %s AND user_id = %s
        """, (application_id, current_user['id']))

        application = cursor.fetchone()

        cursor.close()
        conn.close()

        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        return application

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/applications/{application_id}")
@app.patch("/api/applications/{application_id}")
async def update_application(application_id: int, update: ApplicationUpdate, current_user: dict = Depends(get_current_user)):
    """
    Update an application (requires authentication, must be owner)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Build dynamic update query
        updates = []
        params = []

        if update.job_title is not None:
            updates.append("job_title = %s")
            params.append(update.job_title)

        if update.company is not None:
            updates.append("company = %s")
            params.append(update.company)

        if update.location is not None:
            updates.append("location = %s")
            params.append(update.location)

        if update.job_url is not None:
            updates.append("job_url = %s")
            params.append(update.job_url)

        if update.job_description is not None:
            updates.append("job_description = %s")
            params.append(update.job_description)

        if update.status is not None:
            updates.append("status = %s")
            params.append(update.status)

        if update.deadline is not None:
            updates.append("deadline = %s")
            params.append(update.deadline)

        if update.follow_up_date is not None:
            updates.append("follow_up_date = %s")
            params.append(update.follow_up_date)

        if update.notes is not None:
            updates.append("notes = %s")
            params.append(update.notes)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([application_id, current_user['id']])

        query = f"UPDATE applications SET {', '.join(updates)} WHERE id = %s AND user_id = %s RETURNING id"

        cursor.execute(query, params)
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Application not found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Application updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/applications/{application_id}")
async def delete_application(application_id: int, current_user: dict = Depends(get_current_user)):
    """
    Delete an application (requires authentication, must be owner)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM applications WHERE id = %s AND user_id = %s RETURNING id", (application_id, current_user['id']))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Application not found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Application deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """
    Get dashboard statistics for current user (requires authentication)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Total applications by status for current user
        cursor.execute("""
            SELECT
                status,
                COUNT(*) as count
            FROM applications
            WHERE user_id = %s
            GROUP BY status
        """, (current_user['id'],))
        status_counts = cursor.fetchall()

        # Upcoming deadlines (next 7 days) for current user
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM applications
            WHERE user_id = %s
            AND deadline IS NOT NULL
            AND deadline BETWEEN NOW() AND NOW() + INTERVAL '7 days'
        """, (current_user['id'],))
        upcoming_deadlines = cursor.fetchone()

        # Applications this week for current user
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM applications
            WHERE user_id = %s
            AND applied_date >= NOW() - INTERVAL '7 days'
        """, (current_user['id'],))
        this_week = cursor.fetchone()

        # Get total count
        cursor.execute("""
            SELECT COUNT(*) as count FROM applications WHERE user_id = %s
        """, (current_user['id'],))
        total = cursor.fetchone()

        # Get interview sessions count
        cursor.execute("""
            SELECT COUNT(*) as count FROM interview_sessions WHERE user_id = %s
        """, (current_user['id'],))
        interview_sessions = cursor.fetchone()

        cursor.close()
        conn.close()

        # Convert status_counts array to object
        by_status = {}
        for item in status_counts:
            by_status[item['status']] = item['count']

        return {
            "total": total['count'],
            "by_status": by_status,
            "upcoming_deadlines": upcoming_deadlines['count'],
            "applications_this_week": this_week['count'],
            "interview_sessions": interview_sessions['count']
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ WORK EXPERIENCE ENDPOINTS ============

@app.post("/api/work-experience", response_model=dict)
async def create_work_experience(experience: WorkExperienceCreate, current_user: dict = Depends(get_current_user)):
    """Create a new work experience entry"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            INSERT INTO work_experiences (user_id, company, title, start_date, end_date, is_current, responsibilities)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            current_user['id'],
            experience.company,
            experience.title,
            experience.start_date,
            experience.end_date,
            experience.is_current,
            experience.responsibilities
        ))

        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Work experience created successfully", "id": result['id']}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/work-experience", response_model=List[dict])
async def get_work_experiences(current_user: dict = Depends(get_current_user)):
    """Get all work experiences for current user"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT * FROM work_experiences
            WHERE user_id = %s
            ORDER BY is_current DESC, end_date DESC NULLS FIRST, start_date DESC
        """, (current_user['id'],))

        experiences = cursor.fetchall()
        cursor.close()
        conn.close()

        return experiences

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/work-experience/{experience_id}", response_model=dict)
async def get_work_experience(experience_id: int, current_user: dict = Depends(get_current_user)):
    """Get a specific work experience"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT * FROM work_experiences WHERE id = %s AND user_id = %s
        """, (experience_id, current_user['id']))

        experience = cursor.fetchone()
        cursor.close()
        conn.close()

        if not experience:
            raise HTTPException(status_code=404, detail="Work experience not found")

        return experience

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/work-experience/{experience_id}", response_model=dict)
async def update_work_experience(experience_id: int, update: WorkExperienceUpdate, current_user: dict = Depends(get_current_user)):
    """Update a work experience"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        updates = []
        params = []

        if update.company is not None:
            updates.append("company = %s")
            params.append(update.company)
        if update.title is not None:
            updates.append("title = %s")
            params.append(update.title)
        if update.start_date is not None:
            updates.append("start_date = %s")
            params.append(update.start_date)
        if update.end_date is not None:
            updates.append("end_date = %s")
            params.append(update.end_date)
        if update.is_current is not None:
            updates.append("is_current = %s")
            params.append(update.is_current)
        if update.responsibilities is not None:
            updates.append("responsibilities = %s")
            params.append(update.responsibilities)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.extend([experience_id, current_user['id']])
        query = f"UPDATE work_experiences SET {', '.join(updates)} WHERE id = %s AND user_id = %s RETURNING id"

        cursor.execute(query, params)
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Work experience not found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Work experience updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/work-experience/{experience_id}", response_model=dict)
async def delete_work_experience(experience_id: int, current_user: dict = Depends(get_current_user)):
    """Delete a work experience"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM work_experiences WHERE id = %s AND user_id = %s RETURNING id", (experience_id, current_user['id']))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Work experience not found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Work experience deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ EDUCATION ENDPOINTS ============

@app.post("/api/education", response_model=dict)
async def create_education(education: EducationCreate, current_user: dict = Depends(get_current_user)):
    """Create a new education entry"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            INSERT INTO education (user_id, school, degree, field_of_study, start_date, end_date, gpa)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            current_user['id'],
            education.school,
            education.degree,
            education.field_of_study,
            education.start_date,
            education.end_date,
            education.gpa
        ))

        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Education created successfully", "id": result['id']}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/education", response_model=List[dict])
async def get_education_list(current_user: dict = Depends(get_current_user)):
    """Get all education entries for current user"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT * FROM education
            WHERE user_id = %s
            ORDER BY end_date DESC NULLS FIRST, start_date DESC
        """, (current_user['id'],))

        education = cursor.fetchall()
        cursor.close()
        conn.close()

        return education

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/education/{education_id}", response_model=dict)
async def get_education(education_id: int, current_user: dict = Depends(get_current_user)):
    """Get a specific education entry"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT * FROM education WHERE id = %s AND user_id = %s
        """, (education_id, current_user['id']))

        education = cursor.fetchone()
        cursor.close()
        conn.close()

        if not education:
            raise HTTPException(status_code=404, detail="Education not found")

        return education

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/education/{education_id}", response_model=dict)
async def update_education(education_id: int, update: EducationUpdate, current_user: dict = Depends(get_current_user)):
    """Update an education entry"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        updates = []
        params = []

        if update.school is not None:
            updates.append("school = %s")
            params.append(update.school)
        if update.degree is not None:
            updates.append("degree = %s")
            params.append(update.degree)
        if update.field_of_study is not None:
            updates.append("field_of_study = %s")
            params.append(update.field_of_study)
        if update.start_date is not None:
            updates.append("start_date = %s")
            params.append(update.start_date)
        if update.end_date is not None:
            updates.append("end_date = %s")
            params.append(update.end_date)
        if update.gpa is not None:
            updates.append("gpa = %s")
            params.append(update.gpa)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.extend([education_id, current_user['id']])
        query = f"UPDATE education SET {', '.join(updates)} WHERE id = %s AND user_id = %s RETURNING id"

        cursor.execute(query, params)
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Education not found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Education updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/education/{education_id}", response_model=dict)
async def delete_education(education_id: int, current_user: dict = Depends(get_current_user)):
    """Delete an education entry"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM education WHERE id = %s AND user_id = %s RETURNING id", (education_id, current_user['id']))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Education not found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Education deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ SKILLS ENDPOINTS ============

@app.post("/api/skills", response_model=dict)
async def create_skill(skill: SkillCreate, current_user: dict = Depends(get_current_user)):
    """Create a new skill"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            INSERT INTO skills (user_id, skill_name, proficiency)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (
            current_user['id'],
            skill.skill_name,
            skill.proficiency
        ))

        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Skill created successfully", "id": result['id']}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/skills", response_model=List[dict])
async def get_skills(current_user: dict = Depends(get_current_user)):
    """Get all skills for current user"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT * FROM skills
            WHERE user_id = %s
            ORDER BY skill_name ASC
        """, (current_user['id'],))

        skills = cursor.fetchall()
        cursor.close()
        conn.close()

        return skills

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/skills/{skill_id}", response_model=dict)
async def get_skill(skill_id: int, current_user: dict = Depends(get_current_user)):
    """Get a specific skill"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT * FROM skills WHERE id = %s AND user_id = %s
        """, (skill_id, current_user['id']))

        skill = cursor.fetchone()
        cursor.close()
        conn.close()

        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")

        return skill

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/skills/{skill_id}", response_model=dict)
async def update_skill(skill_id: int, update: SkillUpdate, current_user: dict = Depends(get_current_user)):
    """Update a skill"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        updates = []
        params = []

        if update.skill_name is not None:
            updates.append("skill_name = %s")
            params.append(update.skill_name)
        if update.proficiency is not None:
            updates.append("proficiency = %s")
            params.append(update.proficiency)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.extend([skill_id, current_user['id']])
        query = f"UPDATE skills SET {', '.join(updates)} WHERE id = %s AND user_id = %s RETURNING id"

        cursor.execute(query, params)
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Skill not found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Skill updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/skills/{skill_id}", response_model=dict)
async def delete_skill(skill_id: int, current_user: dict = Depends(get_current_user)):
    """Delete a skill"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM skills WHERE id = %s AND user_id = %s RETURNING id", (skill_id, current_user['id']))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Skill not found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Skill deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ PROJECTS ENDPOINTS ============

@app.post("/api/projects", response_model=dict)
async def create_project(project: ProjectCreate, current_user: dict = Depends(get_current_user)):
    """Create a new project"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            INSERT INTO projects (user_id, title, description, technologies, url, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            current_user['id'],
            project.title,
            project.description,
            project.technologies,
            project.url,
            project.start_date,
            project.end_date
        ))

        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Project created successfully", "id": result['id']}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects", response_model=List[dict])
async def get_projects(current_user: dict = Depends(get_current_user)):
    """Get all projects for current user"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT * FROM projects
            WHERE user_id = %s
            ORDER BY end_date DESC NULLS FIRST, start_date DESC
        """, (current_user['id'],))

        projects = cursor.fetchall()
        cursor.close()
        conn.close()

        return projects

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects/{project_id}", response_model=dict)
async def get_project(project_id: int, current_user: dict = Depends(get_current_user)):
    """Get a specific project"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT * FROM projects WHERE id = %s AND user_id = %s
        """, (project_id, current_user['id']))

        project = cursor.fetchone()
        cursor.close()
        conn.close()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return project

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/projects/{project_id}", response_model=dict)
async def update_project(project_id: int, update: ProjectUpdate, current_user: dict = Depends(get_current_user)):
    """Update a project"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        updates = []
        params = []

        if update.title is not None:
            updates.append("title = %s")
            params.append(update.title)
        if update.description is not None:
            updates.append("description = %s")
            params.append(update.description)
        if update.technologies is not None:
            updates.append("technologies = %s")
            params.append(update.technologies)
        if update.url is not None:
            updates.append("url = %s")
            params.append(update.url)
        if update.start_date is not None:
            updates.append("start_date = %s")
            params.append(update.start_date)
        if update.end_date is not None:
            updates.append("end_date = %s")
            params.append(update.end_date)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.extend([project_id, current_user['id']])
        query = f"UPDATE projects SET {', '.join(updates)} WHERE id = %s AND user_id = %s RETURNING id"

        cursor.execute(query, params)
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Project not found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Project updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/projects/{project_id}", response_model=dict)
async def delete_project(project_id: int, current_user: dict = Depends(get_current_user)):
    """Delete a project"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM projects WHERE id = %s AND user_id = %s RETURNING id", (project_id, current_user['id']))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Project not found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Project deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ COMPLETE RESUME ENDPOINT ============

@app.get("/api/resume", response_model=dict)
async def get_complete_resume(current_user: dict = Depends(get_current_user)):
    """Get complete resume data for current user"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get work experiences
        cursor.execute("""
            SELECT * FROM work_experiences WHERE user_id = %s
            ORDER BY is_current DESC, end_date DESC NULLS FIRST
        """, (current_user['id'],))
        work_experiences = cursor.fetchall()

        # Get education
        cursor.execute("""
            SELECT * FROM education WHERE user_id = %s
            ORDER BY end_date DESC NULLS FIRST
        """, (current_user['id'],))
        education = cursor.fetchall()

        # Get skills
        cursor.execute("""
            SELECT * FROM skills WHERE user_id = %s ORDER BY skill_name
        """, (current_user['id'],))
        skills = cursor.fetchall()

        # Get projects
        cursor.execute("""
            SELECT * FROM projects WHERE user_id = %s
            ORDER BY end_date DESC NULLS FIRST
        """, (current_user['id'],))
        projects = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            "user": {
                "id": current_user['id'],
                "name": current_user['name'],
                "email": current_user['email'],
                "phone": current_user['phone'],
                "location": current_user['location']
            },
            "work_experiences": work_experiences,
            "education": education,
            "skills": skills,
            "projects": projects
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{user_id}/resume/download")
async def download_resume(user_id: int, current_user: dict = Depends(get_current_user)):
    """
    Generate and download resume as DOCX
    """
    # Make sure user can only download their own resume
    if current_user['id'] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this resume")
    
    try:
        # Generate resume
        resume_file = generate_resume(user_id)
        
        # Return as downloadable file
        return StreamingResponse(
            resume_file,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename=resume_{current_user['name'].replace(' ', '_')}.docx"
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/users/{user_id}/resume/analyze", response_model=ResumeAnalysisResponse)
async def analyze_user_resume(
    user_id: int,
    request: ResumeAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze how well user's resume matches a specific job description
    """
    if current_user['id'] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        # Get user resume data
        user_data = get_user_resume_data(user_id)

        # Analyze match using the provided job description
        analysis = analyze_resume_match(user_data, request.job_description)

        return analysis

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/{user_id}/resume/tailor")
async def create_tailored_resume(
    user_id: int,
    request: TailoredResumeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate a tailored resume DOCX file for a specific job
    Returns the tailored resume as a downloadable file
    """
    if current_user['id'] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        # Get user resume data
        user_data = get_user_resume_data(user_id)

        # Generate tailored content using AI
        tailored_data = tailor_resume(user_data, request.job_description, request.job_title)

        # Generate the tailored resume DOCX
        resume_file = generate_tailored_resume(tailored_data, request.job_title)

        # Create safe filename
        safe_job_title = request.job_title.replace(' ', '_').replace('/', '-')[:30]
        filename = f"tailored_resume_{safe_job_title}.docx"

        return StreamingResponse(
            resume_file,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))








# ============ INTERVIEW ENDPOINTS ============

@app.post("/api/interview/start", response_model=dict)
async def start_interview_session(
    request: InterviewSessionCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Start a new interview session with job title and description
    Generates questions and saves to database
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Create interview session with provided job details
        cursor.execute("""
            INSERT INTO interview_sessions (user_id, job_title, job_description)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (current_user['id'], request.job_title, request.job_description))

        session = cursor.fetchone()
        session_id = session['id']

        # Generate interview questions using AI
        questions_data = generate_interview_questions(
            request.job_description,
            request.job_title,
            request.num_questions
        )

        # Save questions to database
        saved_questions = []
        for q in questions_data.get('questions', []):
            cursor.execute("""
                INSERT INTO interview_questions (session_id, question_type, question_text)
                VALUES (%s, %s, %s)
                RETURNING id, question_type, question_text
            """, (session_id, q['type'], q['text']))
            saved_q = cursor.fetchone()
            saved_questions.append({
                "id": saved_q['id'],
                "type": saved_q['question_type'],
                "text": saved_q['question_text'],
                "user_answer": None,
                "ai_feedback": None,
                "score": None
            })

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "session_id": session_id,
            "job_title": request.job_title,
            "questions": saved_questions
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/interview/{session_id}/questions", response_model=dict)
async def get_interview_questions(
    session_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all questions for an interview session
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Verify session belongs to user
        cursor.execute("""
            SELECT id FROM interview_sessions
            WHERE id = %s AND user_id = %s
        """, (session_id, current_user['id']))

        if not cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Session not found")

        # Get questions
        cursor.execute("""
            SELECT id, question_type as type, question_text as text, user_answer, ai_feedback, score
            FROM interview_questions
            WHERE session_id = %s
            ORDER BY id
        """, (session_id,))

        questions = cursor.fetchall()
        cursor.close()
        conn.close()

        return {"questions": questions}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/interview/{session_id}/answer", response_model=InterviewFeedback)
async def submit_interview_answer(
    session_id: int,
    request: AnswerSubmit,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit an answer to an interview question and get AI feedback
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Verify session belongs to user and get job info
        cursor.execute("""
            SELECT id, job_title, job_description
            FROM interview_sessions
            WHERE id = %s AND user_id = %s
        """, (session_id, current_user['id']))

        session = cursor.fetchone()
        if not session:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Session not found")

        # Get the question
        cursor.execute("""
            SELECT id, question_text FROM interview_questions
            WHERE id = %s AND session_id = %s
        """, (request.question_id, session_id))

        question = cursor.fetchone()
        if not question:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Question not found")

        # Get AI feedback
        feedback = evaluate_answer(
            question['question_text'],
            request.answer,
            session['job_title'],
            session['job_description']
        )

        # Save answer and feedback to database
        cursor.execute("""
            UPDATE interview_questions
            SET user_answer = %s,
                ai_feedback = %s,
                score = %s,
                strengths = %s,
                weaknesses = %s,
                suggestions = %s,
                answered_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            request.answer,
            json.dumps(feedback),
            feedback.get('score', 0),
            feedback.get('strengths', []),
            feedback.get('weaknesses', []),
            feedback.get('suggestions', []),
            request.question_id
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return InterviewFeedback(
            score=feedback.get('score', 0),
            strengths=feedback.get('strengths', []),
            weaknesses=feedback.get('weaknesses', []),
            suggestions=feedback.get('suggestions', [])
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/interview/{session_id}/feedback", response_model=dict)
async def get_interview_session_feedback(
    session_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get overall feedback for the entire interview session
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Verify session belongs to user
        cursor.execute("""
            SELECT id FROM interview_sessions
            WHERE id = %s AND user_id = %s
        """, (session_id, current_user['id']))

        if not cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Session not found")

        cursor.close()
        conn.close()

        # Get overall feedback from AI
        overall_feedback = get_overall_feedback(session_id)

        return overall_feedback

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/interview/sessions", response_model=List[dict])
async def get_user_interview_sessions(
    current_user: dict = Depends(get_current_user)
):
    """
    Get all interview sessions for the current user
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT
                s.id,
                s.job_title,
                s.created_at,
                COUNT(q.id) as total_questions,
                COUNT(q.user_answer) as answered_questions,
                AVG(q.score) as average_score,
                CASE WHEN COUNT(q.id) > 0 AND COUNT(q.user_answer) = COUNT(q.id) THEN true ELSE false END as is_completed
            FROM interview_sessions s
            LEFT JOIN interview_questions q ON s.id = q.session_id
            WHERE s.user_id = %s
            GROUP BY s.id
            ORDER BY s.created_at DESC
        """, (current_user['id'],))

        sessions = cursor.fetchall()
        cursor.close()
        conn.close()

        return sessions

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)