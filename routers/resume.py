from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from psycopg2.extras import RealDictCursor
from services.database import get_connection
from services.resume_generator import generate_resume, generate_tailored_resume
from services.resume_ai import get_user_resume_data, analyze_resume_match, tailor_resume
from models.resume import ResumeAnalysisRequest, ResumeAnalysisResponse, TailoredResumeRequest
from auth.dependencies import get_current_user

router = APIRouter(tags=["Resume"])


@router.get("/api/resume", response_model=dict)
async def get_complete_resume(current_user: dict = Depends(get_current_user)):
    """Get complete resume data for current user"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get work experiences
        cursor.execute("""
            SELECT * FROM work_experiences WHERE user_id = %s
            ORDER BY is_current DESC, end_date DESC NULLS FIRST
        """, (current_user['id'],))
        work_experiences = cursor.fetchall()

        # Get education
        cursor.execute("""
            SELECT * FROM education WHERE user_id = %s
            ORDER BY end_date DESC NULLS FIRST
        """, (current_user['id'],))
        education = cursor.fetchall()

        # Get skills
        cursor.execute("""
            SELECT * FROM skills WHERE user_id = %s ORDER BY skill_name
        """, (current_user['id'],))
        skills = cursor.fetchall()

        # Get projects
        cursor.execute("""
            SELECT * FROM projects WHERE user_id = %s
            ORDER BY end_date DESC NULLS FIRST
        """, (current_user['id'],))
        projects = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            "user": {
                "id": current_user['id'],
                "name": current_user['name'],
                "email": current_user['email'],
                "phone": current_user['phone'],
                "location": current_user['location']
            },
            "work_experiences": work_experiences,
            "education": education,
            "skills": skills,
            "projects": projects
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/users/{user_id}/resume/download")
async def download_resume(user_id: int, current_user: dict = Depends(get_current_user)):
    """
    Generate and download resume as DOCX
    """
    # Make sure user can only download their own resume
    if current_user['id'] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this resume")

    try:
        # Generate resume
        resume_file = generate_resume(user_id)

        # Return as downloadable file
        return StreamingResponse(
            resume_file,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename=resume_{current_user['name'].replace(' ', '_')}.docx"
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/users/{user_id}/resume/analyze", response_model=ResumeAnalysisResponse)
async def analyze_user_resume(
    user_id: int,
    request: ResumeAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze how well user's resume matches a specific job description
    """
    if current_user['id'] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        # Get user resume data
        user_data = get_user_resume_data(user_id)

        # Analyze match using the provided job description
        analysis = analyze_resume_match(user_data, request.job_description)

        return analysis

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/users/{user_id}/resume/tailor")
async def create_tailored_resume(
    user_id: int,
    request: TailoredResumeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate a tailored resume DOCX file for a specific job
    Returns the tailored resume as a downloadable file
    """
    if current_user['id'] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        # Get user resume data
        user_data = get_user_resume_data(user_id)

        # Generate tailored content using AI
        tailored_data = tailor_resume(user_data, request.job_description, request.job_title)

        # Generate the tailored resume DOCX
        resume_file = generate_tailored_resume(tailored_data, request.job_title)

        # Create safe filename
        safe_job_title = request.job_title.replace(' ', '_').replace('/', '-')[:30]
        filename = f"tailored_resume_{safe_job_title}.docx"

        return StreamingResponse(
            resume_file,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
