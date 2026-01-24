from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from psycopg2.extras import RealDictCursor
from services.database import get_connection
from models.application import ApplicationCreate, ApplicationUpdate
from auth.dependencies import get_current_user

router = APIRouter(prefix="/api/applications", tags=["Applications"])


@router.post("", response_model=dict)
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


@router.get("", response_model=List[dict])
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


@router.get("/{application_id}")
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


@router.put("/{application_id}")
@router.patch("/{application_id}")
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


@router.delete("/{application_id}")
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
