from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from psycopg2.extras import RealDictCursor
import psycopg2
import uuid
from services.database import get_connection
from services.scraper import fetch_jobs
from models.job import Job, JobSave, JobSearchRequest
from auth.dependencies import get_current_user

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post("/search", response_model=dict)
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
            max_jobs=request.max_jobs
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


@router.post("", response_model=dict)
async def save_job(job: JobSave, current_user: dict = Depends(get_current_user)):
    """
    Save a job to the database for the current user (requires authentication)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Generate a unique job_id
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


@router.delete("/{job_id}")
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


@router.get("", response_model=List[Job])
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


@router.get("/{job_id}")
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
