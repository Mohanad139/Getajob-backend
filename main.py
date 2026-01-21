from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from database import get_connection
from scraper import fetch_jobs, save_jobs_to_db
import os
from datetime import datetime, timedelta


app = FastAPI(title="Interview AI API")

# Enable CORS for your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
async def create_application(application: ApplicationCreate):
    """
    Mark a job as applied with optional deadline
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if job exists
        cursor.execute("SELECT job_id FROM jobs WHERE job_id = %s", (application.job_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Check if already applied
        cursor.execute("SELECT id FROM applications WHERE job_id = %s", (application.job_id,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Already applied to this job")
        
        # Insert application
        cursor.execute("""
            INSERT INTO applications (job_id, status, deadline, follow_up_date, notes)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            application.job_id,
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
    upcoming_deadlines: Optional[bool] = False
):
    """
    Get all applications with optional filters
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
            WHERE 1=1
        """
        params = []
        
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
async def get_application(application_id: int):
    """
    Get a specific application
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
            WHERE a.id = %s
        """, (application_id,))
        
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
async def update_application(application_id: int, update: ApplicationUpdate):
    """
    Update an application (status, deadline, notes)
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
        params.append(application_id)
        
        query = f"UPDATE applications SET {', '.join(updates)} WHERE id = %s RETURNING id"
        
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
async def delete_application(application_id: int):
    """
    Delete an application
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM applications WHERE id = %s RETURNING id", (application_id,))
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
async def get_dashboard_stats():
    """
    Get dashboard statistics
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Total applications by status
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM applications
            GROUP BY status
        """)
        status_counts = cursor.fetchall()
        
        # Upcoming deadlines (next 7 days)
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM applications
            WHERE deadline IS NOT NULL 
            AND deadline BETWEEN NOW() AND NOW() + INTERVAL '7 days'
        """)
        upcoming_deadlines = cursor.fetchone()
        
        # Applications this week
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM applications
            WHERE applied_date >= NOW() - INTERVAL '7 days'
        """)
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

