from fastapi import APIRouter, HTTPException, Depends
from typing import List
from psycopg2.extras import RealDictCursor
from services.database import get_connection
from models.resume import EducationCreate, EducationUpdate
from auth.dependencies import get_current_user

router = APIRouter(prefix="/api/education", tags=["Education"])


@router.post("", response_model=dict)
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


@router.get("", response_model=List[dict])
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


@router.get("/{education_id}", response_model=dict)
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


@router.patch("/{education_id}", response_model=dict)
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


@router.delete("/{education_id}", response_model=dict)
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
