from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from psycopg2.extras import RealDictCursor
from typing import Optional
from services.database import get_connection
from .utils import decode_access_token

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    token_data = decode_access_token(token)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        "SELECT id, email, name, phone, location, headline, summary, created_at FROM users WHERE id = %s",
        (token_data.user_id,)
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user


async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security)) -> Optional[dict]:
    """
    Optional authentication - returns user if authenticated, None otherwise.
    Use this for endpoints that work with or without authentication.
    """
    if credentials is None:
        return None

    token = credentials.credentials
    token_data = decode_access_token(token)

    if token_data is None:
        return None

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        "SELECT id, email, name, phone, location, headline, summary, created_at FROM users WHERE id = %s",
        (token_data.user_id,)
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return user
