from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, date, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from database import get_connection
from scraper import fetch_jobs, save_jobs_to_db
import os
from dotenv import load_dotenv
import jwt
import bcrypt

# Load environment variables
load_dotenv()

# JWT Settings
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

app = FastAPI(title="Interview AI API")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

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
    email: EmailStr
    password: str
    full_name: str

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
    full_name: str
    created_at: datetime

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

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data = decode_access_token(token)
    if token_data is None:
        raise credentials_exception

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT id, email, full_name, created_at FROM users WHERE id = %s", (token_data.user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user is None:
        raise credentials_exception
    return user

# ============ WORK EXPERIENCE MODELS ============

class WorkExperienceCreate(BaseModel):
    user_id: int
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
    user_id: int
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
    user_id: int
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
    user_id: int
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
    work_experiences: List[WorkExperience]
    education: List[Education]
    skills: List[Skill]
    projects: List[Project]



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
    job_id: str
    status: Optional[str] = "applied"
    deadline: Optional[str] = None  # ISO format: "2026-01-25T10:00:00"
    follow_up_date: Optional[str] = None
    notes: Optional[str] = None

class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    deadline: Optional[str] = None
    follow_up_date: Optional[str] = None
    notes: Optional[str] = None

class Application(BaseModel):
    id: int
    job_id: str
    status: str
    applied_date: str
    deadline: Optional[str]
    follow_up_date: Optional[str]
    notes: Optional[str]
    created_at: str
    updated_at: str



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
            INSERT INTO users (email, password_hash, full_name)
            VALUES (%s, %s, %s)
            RETURNING id, email, full_name
        """, (user.email, hashed_password, user.full_name))

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
                "full_name": new_user['full_name']
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/login", response_model=dict)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Find user by email (username field contains email)
        cursor.execute(
            "SELECT id, email, password_hash, full_name FROM users WHERE email = %s",
            (form_data.username,)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or not verify_password(form_data.password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
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
                "full_name": user['full_name']
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
        "full_name": current_user['full_name']
    }

# ============ JOB ENDPOINTS ============

@app.post("/api/jobs/search", response_model=JobSearchResponse)
async def search_jobs(request: JobSearchRequest):
    """
    Endpoint to search and fetch jobs from JSearch API
    """
    try:
        # Fetch jobs from API
        jobs = fetch_jobs(
            query=request.query,
            location=request.location,
            num_pages=request.num_pages
        )
        
        if not jobs:
            return JobSearchResponse(
                message="No jobs found",
                jobs_fetched=0,
                jobs_saved=0
            )

        # Filter jobs by location if specified
        if request.location:
            location_lower = request.location.lower()
            jobs = [
                job for job in jobs
                if location_lower in (job.get('job_city', '') or '').lower()
                or location_lower in (job.get('job_country', '') or '').lower()
                or location_lower in (job.get('job_state', '') or '').lower()
            ]

        # Save to database
        saved_count = save_jobs_to_db(jobs)
        
        return JobSearchResponse(
            message="Jobs fetched and saved successfully",
            jobs_fetched=len(jobs),
            jobs_saved=saved_count
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs", response_model=List[Job])
async def get_jobs(
    limit: int = 10,
    offset: int = 0,
    company: Optional[str] = None,
    location: Optional[str] = None
):
    """
    Endpoint to get jobs from database with filters
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build query with filters
        query = "SELECT * FROM jobs WHERE 1=1"
        params = []

        if company:
            query += " AND company ILIKE %s"
            params.append(f"%{company}%")

        if location:
            query += " AND location ILIKE %s"
            params.append(f"{location}%")
        
        query += " ORDER BY posted_date DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
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
    Mark a job as applied with optional deadline (requires authentication)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Check if job exists
        cursor.execute("SELECT job_id FROM jobs WHERE job_id = %s", (application.job_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Job not found")

        # Check if user already applied to this job
        cursor.execute("SELECT id FROM applications WHERE job_id = %s AND user_id = %s", (application.job_id, current_user['id']))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Already applied to this job")

        # Insert application with user_id
        cursor.execute("""
            INSERT INTO applications (job_id, user_id, status, deadline, follow_up_date, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            application.job_id,
            current_user['id'],
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
            SELECT
                a.*,
                j.title,
                j.company,
                j.location,
                j.url
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            WHERE a.user_id = %s
        """
        params = [current_user['id']]

        if status:
            query += " AND a.status = %s"
            params.append(status)

        if upcoming_deadlines:
            query += " AND a.deadline IS NOT NULL AND a.deadline > NOW()"
            query += " ORDER BY a.deadline ASC"
        else:
            query += " ORDER BY a.applied_date DESC"

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
            SELECT
                a.*,
                j.title,
                j.company,
                j.location,
                j.url,
                j.description
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            WHERE a.id = %s AND a.user_id = %s
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

        cursor.close()
        conn.close()

        return {
            "status_breakdown": status_counts,
            "upcoming_deadlines": upcoming_deadlines['count'],
            "applications_this_week": this_week['count']
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))







if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

