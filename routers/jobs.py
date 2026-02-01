from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional, List
from psycopg2.extras import RealDictCursor
import psycopg2
import uuid
from services.database import get_connection
from services.scraper import fetch_jobs
from services.rate_limiter import limiter
from models.job import Job, JobSave, JobSkip, JobSearchRequest, SkippedJob
from auth.dependencies import get_current_user, get_optional_user

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post("/search", response_model=dict)
@limiter.limit("10/minute")  # 10 searches per minute per user/IP
async def search_jobs(request: Request, search_request: JobSearchRequest, current_user: Optional[dict] = Depends(get_optional_user)):
    """
    Endpoint to search and fetch jobs from JSearch API
    Returns the jobs directly for display (does NOT auto-save)
    Query should include location, e.g. "Software Engineer in Canada"
    If authenticated, filters out jobs the user has already saved or skipped.
    """
    try:
        # Fetch jobs from API - query should include location
        raw_jobs = fetch_jobs(
            query=search_request.query,
            location="",
            max_jobs=search_request.max_jobs,
            date_posted=search_request.date_posted,
            sort_by=search_request.sort_by,
            refresh=search_request.refresh
        )

        if not raw_jobs:
            return {"jobs": [], "message": "No jobs found"}

        # Get user's saved and skipped jobs if authenticated
        excluded_jobs = set()
        if current_user:
            conn = get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Get saved jobs (title, company, location)
            cursor.execute(
                "SELECT title, company, location FROM jobs WHERE user_id = %s",
                (current_user['id'],)
            )
            for row in cursor.fetchall():
                key = (row['title'].lower(), row['company'].lower(), (row['location'] or '').lower())
                excluded_jobs.add(key)

            # Get skipped jobs (title, company, location)
            cursor.execute(
                "SELECT title, company, location FROM skipped_jobs WHERE user_id = %s",
                (current_user['id'],)
            )
            for row in cursor.fetchall():
                key = (row['title'].lower(), row['company'].lower(), (row['location'] or '').lower())
                excluded_jobs.add(key)

            cursor.close()
            conn.close()

        # Transform jobs to a simpler format for the frontend
        jobs = []
        filtered_count = 0
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

            title = job.get('job_title', '') or ''
            company = job.get('employer_name', '') or ''

            # Skip if user has already saved or skipped this job
            if current_user:
                job_key = (title.lower(), company.lower(), job_location.lower())
                if job_key in excluded_jobs:
                    filtered_count += 1
                    continue

            jobs.append({
                "title": title,
                "company": company,
                "location": job_location,
                "salary": salary,
                "description": (job.get('job_description', '') or '')[:500],
                "url": job.get('job_apply_link', '') or job.get('job_google_link', '') or '',
                "job_type": job.get('job_employment_type', '') or '',
                "posted_date": job.get('job_posted_at_datetime_utc', '') or ''
            })

        # Jobs are NOT auto-saved - user must explicitly save
        message = f"Found {len(jobs)} jobs"
        if filtered_count > 0:
            message += f" ({filtered_count} already saved/skipped)"
        return {"jobs": jobs, "message": message}

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


@router.post("/skip", response_model=dict)
async def skip_job(job: JobSkip, current_user: dict = Depends(get_current_user)):
    """
    Mark a job as skipped so it won't appear in future searches (requires authentication)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO skipped_jobs (user_id, title, company, location)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, title, company, location) DO NOTHING
        """, (
            current_user['id'],
            job.title,
            job.company,
            job.location or ''
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Job skipped successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skipped", response_model=List[SkippedJob])
async def get_skipped_jobs(current_user: dict = Depends(get_current_user)):
    """
    Get all skipped jobs for the current user (requires authentication)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            "SELECT id, title, company, location, skipped_at FROM skipped_jobs WHERE user_id = %s ORDER BY skipped_at DESC",
            (current_user['id'],)
        )
        skipped_jobs = cursor.fetchall()

        cursor.close()
        conn.close()

        return skipped_jobs

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/skipped/{skipped_id}")
async def delete_skipped_job(skipped_id: int, current_user: dict = Depends(get_current_user)):
    """
    Remove a job from skipped list so it can appear in searches again (requires authentication)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM skipped_jobs WHERE id = %s AND user_id = %s RETURNING id",
            (skipped_id, current_user['id'])
        )
        result = cursor.fetchone()

        if not result:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Skipped job not found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Job removed from skipped list"}

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
