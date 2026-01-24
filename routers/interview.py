from fastapi import APIRouter, HTTPException, Depends
from typing import List
from psycopg2.extras import RealDictCursor
import json
from services.database import get_connection
from services.interview_ai import generate_interview_questions, evaluate_answer, get_overall_feedback
from models.interview import InterviewSessionCreate, AnswerSubmit, InterviewFeedback
from auth.dependencies import get_current_user

router = APIRouter(prefix="/api/interview", tags=["Interview"])


@router.post("/start", response_model=dict)
async def start_interview_session(
    request: InterviewSessionCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Start a new interview session with job title and description
    Generates questions and saves to database
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Create interview session with provided job details
        cursor.execute("""
            INSERT INTO interview_sessions (user_id, job_title, job_description)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (current_user['id'], request.job_title, request.job_description))

        session = cursor.fetchone()
        session_id = session['id']

        # Generate interview questions using AI
        questions_data = generate_interview_questions(
            request.job_description,
            request.job_title,
            request.num_questions
        )

        # Save questions to database
        saved_questions = []
        for q in questions_data.get('questions', []):
            cursor.execute("""
                INSERT INTO interview_questions (session_id, question_type, question_text)
                VALUES (%s, %s, %s)
                RETURNING id, question_type, question_text
            """, (session_id, q['type'], q['text']))
            saved_q = cursor.fetchone()
            saved_questions.append({
                "id": saved_q['id'],
                "type": saved_q['question_type'],
                "text": saved_q['question_text'],
                "user_answer": None,
                "ai_feedback": None,
                "score": None
            })

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "session_id": session_id,
            "job_title": request.job_title,
            "questions": saved_questions
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/questions", response_model=dict)
async def get_interview_questions(
    session_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all questions for an interview session
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Verify session belongs to user
        cursor.execute("""
            SELECT id FROM interview_sessions
            WHERE id = %s AND user_id = %s
        """, (session_id, current_user['id']))

        if not cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Session not found")

        # Get questions
        cursor.execute("""
            SELECT id, question_type as type, question_text as text, user_answer, ai_feedback, score
            FROM interview_questions
            WHERE session_id = %s
            ORDER BY id
        """, (session_id,))

        questions = cursor.fetchall()
        cursor.close()
        conn.close()

        return {"questions": questions}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/answer", response_model=InterviewFeedback)
async def submit_interview_answer(
    session_id: int,
    request: AnswerSubmit,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit an answer to an interview question and get AI feedback
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Verify session belongs to user and get job info
        cursor.execute("""
            SELECT id, job_title, job_description
            FROM interview_sessions
            WHERE id = %s AND user_id = %s
        """, (session_id, current_user['id']))

        session = cursor.fetchone()
        if not session:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Session not found")

        # Get the question
        cursor.execute("""
            SELECT id, question_text FROM interview_questions
            WHERE id = %s AND session_id = %s
        """, (request.question_id, session_id))

        question = cursor.fetchone()
        if not question:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Question not found")

        # Get AI feedback
        feedback = evaluate_answer(
            question['question_text'],
            request.answer,
            session['job_title'],
            session['job_description']
        )

        # Save answer and feedback to database
        cursor.execute("""
            UPDATE interview_questions
            SET user_answer = %s,
                ai_feedback = %s,
                score = %s,
                strengths = %s,
                weaknesses = %s,
                suggestions = %s,
                answered_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            request.answer,
            json.dumps(feedback),
            feedback.get('score', 0),
            feedback.get('strengths', []),
            feedback.get('weaknesses', []),
            feedback.get('suggestions', []),
            request.question_id
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return InterviewFeedback(
            score=feedback.get('score', 0),
            strengths=feedback.get('strengths', []),
            weaknesses=feedback.get('weaknesses', []),
            suggestions=feedback.get('suggestions', [])
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/feedback", response_model=dict)
async def get_interview_session_feedback(
    session_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get overall feedback for the entire interview session
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Verify session belongs to user
        cursor.execute("""
            SELECT id FROM interview_sessions
            WHERE id = %s AND user_id = %s
        """, (session_id, current_user['id']))

        if not cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Session not found")

        cursor.close()
        conn.close()

        # Get overall feedback from AI
        overall_feedback = get_overall_feedback(session_id)

        return overall_feedback

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=List[dict])
async def get_user_interview_sessions(
    current_user: dict = Depends(get_current_user)
):
    """
    Get all interview sessions for the current user
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT
                s.id,
                s.job_title,
                s.created_at,
                COUNT(q.id) as total_questions,
                COUNT(q.user_answer) as answered_questions,
                AVG(q.score) as average_score,
                CASE WHEN COUNT(q.id) > 0 AND COUNT(q.user_answer) = COUNT(q.id) THEN true ELSE false END as is_completed
            FROM interview_sessions s
            LEFT JOIN interview_questions q ON s.id = q.session_id
            WHERE s.user_id = %s
            GROUP BY s.id
            ORDER BY s.created_at DESC
        """, (current_user['id'],))

        sessions = cursor.fetchall()
        cursor.close()
        conn.close()

        return sessions

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
