from fastapi import APIRouter, HTTPException, Depends
from typing import List
from psycopg2.extras import RealDictCursor
from services.database import get_connection
from models.resume import SkillCreate, SkillUpdate
from auth.dependencies import get_current_user

router = APIRouter(prefix="/api/skills", tags=["Skills"])


@router.post("", response_model=dict)
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


@router.get("", response_model=List[dict])
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


@router.get("/{skill_id}", response_model=dict)
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


@router.patch("/{skill_id}", response_model=dict)
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


@router.delete("/{skill_id}", response_model=dict)
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
