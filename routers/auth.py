from fastapi import APIRouter, HTTPException, Depends, status
from psycopg2.extras import RealDictCursor
from services.database import get_connection
from models.auth import UserCreate, UserLogin, UserUpdate
from auth.utils import hash_password, verify_password, create_access_token
from auth.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=dict)
async def register(user: UserCreate):
    """Register a new user"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (user.email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Email already registered")

        # Hash password and create user
        hashed_password = hash_password(user.password)
        cursor.execute("""
            INSERT INTO users (email, password_hash, name, phone, location)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, email, name, phone, location
        """, (user.email, hashed_password, user.name, user.phone, user.location))

        new_user = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        # Create access token
        access_token = create_access_token(
            data={"user_id": new_user['id'], "email": new_user['email']}
        )

        return {
            "message": "User registered successfully",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": new_user['id'],
                "email": new_user['email'],
                "name": new_user['name'],
                "phone": new_user['phone'],
                "location": new_user['location']
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login", response_model=dict)
async def login(credentials: UserLogin):
    """Login and get access token"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Find user by email
        cursor.execute(
            "SELECT id, email, password_hash, name, phone, location FROM users WHERE email = %s",
            (credentials.email,)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or not verify_password(credentials.password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        # Create access token
        access_token = create_access_token(
            data={"user_id": user['id'], "email": user['email']}
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user['id'],
                "email": user['email'],
                "name": user['name'],
                "phone": user['phone'],
                "location": user['location']
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me", response_model=dict)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    return {
        "id": current_user['id'],
        "email": current_user['email'],
        "name": current_user['name'],
        "phone": current_user.get('phone'),
        "location": current_user.get('location'),
        "headline": current_user.get('headline'),
        "summary": current_user.get('summary')
    }


@router.put("/profile", response_model=dict)
async def update_profile(update_data: UserUpdate, current_user: dict = Depends(get_current_user)):
    """Update current user's profile"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Build dynamic update query
        update_fields = []
        params = []

        if update_data.name is not None:
            update_fields.append("name = %s")
            params.append(update_data.name)
        if update_data.phone is not None:
            update_fields.append("phone = %s")
            params.append(update_data.phone)
        if update_data.location is not None:
            update_fields.append("location = %s")
            params.append(update_data.location)
        if update_data.headline is not None:
            update_fields.append("headline = %s")
            params.append(update_data.headline)
        if update_data.summary is not None:
            update_fields.append("summary = %s")
            params.append(update_data.summary)

        if not update_fields:
            return {"message": "No fields to update"}

        params.append(current_user['id'])

        query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s RETURNING *"
        cursor.execute(query, params)
        updated_user = cursor.fetchone()

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "message": "Profile updated successfully",
            "user": {
                "id": updated_user['id'],
                "email": updated_user['email'],
                "name": updated_user['name'],
                "phone": updated_user.get('phone'),
                "location": updated_user.get('location'),
                "headline": updated_user.get('headline'),
                "summary": updated_user.get('summary')
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
