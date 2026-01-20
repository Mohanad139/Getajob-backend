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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)