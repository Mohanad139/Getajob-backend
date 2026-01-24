from fastapi import APIRouter, HTTPException, Depends
from typing import List
from psycopg2.extras import RealDictCursor
from services.database import get_connection
from models.resume import ProjectCreate, ProjectUpdate
from auth.dependencies import get_current_user

router = APIRouter(prefix="/api/projects", tags=["Projects"])


@router.post("", response_model=dict)
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


@router.get("", response_model=List[dict])
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


@router.get("/{project_id}", response_model=dict)
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


@router.patch("/{project_id}", response_model=dict)
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


@router.delete("/{project_id}", response_model=dict)
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
