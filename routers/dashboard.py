from fastapi import APIRouter, HTTPException, Depends
from psycopg2.extras import RealDictCursor
from services.database import get_connection
from auth.dependencies import get_current_user

router = APIRouter(tags=["Dashboard"])


@router.get("/api/stats")
async def get_stats():
    """
    Get database statistics
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT
                COUNT(*) as total_jobs,
                COUNT(DISTINCT company) as total_companies,
                COUNT(DISTINCT location) as total_locations
            FROM jobs
            WHERE is_active = TRUE
        """)
        stats = cursor.fetchone()

        cursor.close()
        conn.close()

        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """
    Get dashboard statistics for current user (requires authentication)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Total applications by status for current user
        cursor.execute("""
            SELECT
                status,
                COUNT(*) as count
            FROM applications
            WHERE user_id = %s
            GROUP BY status
        """, (current_user['id'],))
        status_counts = cursor.fetchall()

        # Upcoming deadlines (next 7 days) for current user
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM applications
            WHERE user_id = %s
            AND deadline IS NOT NULL
            AND deadline BETWEEN NOW() AND NOW() + INTERVAL '7 days'
        """, (current_user['id'],))
        upcoming_deadlines = cursor.fetchone()

        # Applications this week for current user
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM applications
            WHERE user_id = %s
            AND applied_date >= NOW() - INTERVAL '7 days'
        """, (current_user['id'],))
        this_week = cursor.fetchone()

        # Get total count
        cursor.execute("""
            SELECT COUNT(*) as count FROM applications WHERE user_id = %s
        """, (current_user['id'],))
        total = cursor.fetchone()

        # Get interview sessions count
        cursor.execute("""
            SELECT COUNT(*) as count FROM interview_sessions WHERE user_id = %s
        """, (current_user['id'],))
        interview_sessions = cursor.fetchone()

        cursor.close()
        conn.close()

        # Convert status_counts array to object
        by_status = {}
        for item in status_counts:
            by_status[item['status']] = item['count']

        return {
            "total": total['count'],
            "by_status": by_status,
            "upcoming_deadlines": upcoming_deadlines['count'],
            "applications_this_week": this_week['count'],
            "interview_sessions": interview_sessions['count']
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
