from fastapi import APIRouter, HTTPException, Depends
from typing import List
from psycopg2.extras import RealDictCursor
from services.database import get_connection
from models.resume import WorkExperienceCreate, WorkExperienceUpdate
from auth.dependencies import get_current_user

router = APIRouter(prefix="/api/work-experience", tags=["Work Experience"])


@router.post("", response_model=dict)
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


@router.get("", response_model=List[dict])
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


@router.get("/{experience_id}", response_model=dict)
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


@router.patch("/{experience_id}", response_model=dict)
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


@router.delete("/{experience_id}", response_model=dict)
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
