from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from psycopg2.extras import RealDictCursor
from psycopg2 import Binary
import io
from services.database import get_connection
from services.resume_generator import generate_resume, generate_tailored_resume
from services.resume_ai import get_user_resume_data, analyze_resume_match, tailor_resume
from services.resume_parser import extract_text_from_pdf, parse_resume_with_ai, save_parsed_resume_data
from models.resume import ResumeAnalysisRequest, ResumeAnalysisResponse, TailoredResumeRequest, ResumeUploadResponse
from auth.dependencies import get_current_user

router = APIRouter(tags=["Resume"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


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


@router.post("/api/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a PDF resume, store it in the database, and parse it with AI
    to auto-fill the user's profile (work experience, education, skills, projects)
    """
    # Validate file type
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Read file content
    file_bytes = await file.read()

    # Validate file size
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    try:
        # Store PDF in database (upsert - replace if exists)
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM user_resumes WHERE user_id = %s",
            (current_user['id'],)
        )
        cursor.execute("""
            INSERT INTO user_resumes (user_id, filename, file_data, file_size)
            VALUES (%s, %s, %s, %s)
        """, (
            current_user['id'],
            file.filename,
            Binary(file_bytes),
            len(file_bytes)
        ))
        conn.commit()
        cursor.close()
        conn.close()

        # Extract text from PDF
        resume_text = extract_text_from_pdf(file_bytes)

        # Parse with AI
        parsed_data = parse_resume_with_ai(resume_text)

        # Save parsed data to profile tables
        counts = save_parsed_resume_data(current_user['id'], parsed_data)

        return ResumeUploadResponse(
            message="Resume uploaded and parsed successfully",
            filename=file.filename,
            file_size=len(file_bytes),
            parsed_data=parsed_data,
            counts=counts
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/resume/file")
async def get_resume_file(current_user: dict = Depends(get_current_user)):
    """Download the user's uploaded resume PDF"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            "SELECT filename, file_data FROM user_resumes WHERE user_id = %s",
            (current_user['id'],)
        )
        resume = cursor.fetchone()
        cursor.close()
        conn.close()

        if not resume:
            raise HTTPException(status_code=404, detail="No resume file found")

        return StreamingResponse(
            io.BytesIO(bytes(resume['file_data'])),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={resume['filename']}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/resume/file")
async def delete_resume_file(current_user: dict = Depends(get_current_user)):
    """Delete the user's uploaded resume PDF"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM user_resumes WHERE user_id = %s RETURNING id",
            (current_user['id'],)
        )
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="No resume file found")

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Resume file deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
