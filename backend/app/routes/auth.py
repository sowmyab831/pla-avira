"""
Authentication and RBAC Routes
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
import bcrypt
import jwt
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.database import get_session, UserDB, PasswordResetTokenDB
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)
security = HTTPBearer()

# JWT settings
SECRET_KEY = settings.secret_key if hasattr(settings, 'secret_key') else "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "user"


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    username: str
    role: str


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: str


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_session)
) -> UserDB:
    """Get current authenticated user from JWT token."""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    
    result = await db.execute(select(UserDB).filter(UserDB.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    
    return user


security_optional = HTTPBearer(auto_error=False)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_optional),
    db: AsyncSession = Depends(get_session)
) -> UserDB | None:
    """Return the authenticated user if a valid Bearer token is present, else None."""
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
        result = await db.execute(select(UserDB).filter(UserDB.user_id == user_id))
        user = result.scalar_one_or_none()
        return user if user and user.is_active else None
    except Exception:
        return None


async def require_admin(current_user: UserDB = Depends(get_current_user)) -> UserDB:
    """Require admin role for endpoint access."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


@router.post("/init-admin")
async def initialize_admin(db: AsyncSession = Depends(get_session)):
    """
    Initialize default admin account.
    Username: admin
    Password: changeme
    
    This endpoint can only be called once. After admin exists, it will fail.
    """
    try:
        # Check if admin already exists
        result = await db.execute(select(UserDB).filter(UserDB.username == "admin"))
        existing_admin = result.scalar_one_or_none()
        
        if existing_admin:
            raise HTTPException(
                status_code=400,
                detail="Admin account already exists. Use /auth/login to authenticate."
            )
        
        # Create admin user
        admin_user = UserDB(
            user_id=f"user_admin_{int(datetime.utcnow().timestamp())}",
            username="admin",
            email="admin@pla-avira.local",
            password_hash=hash_password("changeme"),
            role="admin",
            is_active=True
        )
        
        db.add(admin_user)
        await db.commit()
        await db.refresh(admin_user)
        
        logger.info("Admin account created successfully")
        
        return {
            "success": True,
            "message": "Admin account created",
            "username": "admin",
            "password": "changeme",
            "warning": "Please change the password immediately after first login"
        }
    except Exception as e:
        logger.error(f"Failed to create admin: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login", response_model=Token)
async def login(user_login: UserLogin, db: AsyncSession = Depends(get_session)):
    """Authenticate user and return JWT token."""
    try:
        result = await db.execute(
            select(UserDB).filter(UserDB.username == user_login.username)
        )
        user = result.scalar_one_or_none()
        
        if not user or not verify_password(user_login.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive"
            )
        
        # Create access token
        access_token = create_access_token(
            data={"sub": user.user_id, "username": user.username, "role": user.role}
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            user_id=user.user_id,
            username=user.username,
            role=user.role
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


# ── Password Reset ───────────────────────────────────────────────────────────
# Reset tokens are persisted in Postgres (password_reset_tokens) so they
# survive pod restarts. Tokens are single-use and expire after 30 minutes.


class ForgotPasswordRequest(BaseModel):
    username_or_email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_session)):
    """Send a password-reset link/code to the account's email via the local mail server."""
    import secrets
    result = await db.execute(
        select(UserDB).filter(
            (UserDB.username == body.username_or_email) | (UserDB.email == body.username_or_email)
        )
    )
    user = result.scalar_one_or_none()

    # Always return success to avoid leaking which accounts exist
    if not user:
        return {"success": True, "message": "If that account exists, a reset email was sent."}

    token = secrets.token_urlsafe(24)
    db.add(PasswordResetTokenDB(
        token=token,
        user_id=user.user_id,
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    ))
    await db.commit()

    from app.services.notification_service import send_email
    email_result = await send_email(
        to_email=user.email,
        subject="Avira — Password Reset",
        body=(
            f"Hi {user.username},\n\n"
            f"Use this code to reset your password (valid 30 minutes):\n\n"
            f"    {token}\n\n"
            f"If you didn't request this, ignore this email."
        ),
    )
    logger.info(f"Password reset email for {user.username}: {email_result}")
    return {"success": True, "message": "If that account exists, a reset email was sent."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_session)):
    """Reset password using a token from the forgot-password email."""
    result = await db.execute(
        select(PasswordResetTokenDB).filter(
            PasswordResetTokenDB.token == body.token,
            PasswordResetTokenDB.used == False,  # noqa: E712
        )
    )
    entry = result.scalar_one_or_none()
    if not entry or entry.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    result = await db.execute(select(UserDB).filter(UserDB.user_id == entry.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user.password_hash = hash_password(body.new_password)
    entry.used = True  # single-use token
    await db.commit()
    logger.info(f"Password reset completed for user {user.username}")
    return {"success": True, "message": "Password updated. You can now log in."}


@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_session),
    admin: UserDB = Depends(require_admin)
):
    """
    Register a new user (admin only).
    Only admins can create new user accounts.
    """
    try:
        # Check if username already exists
        result = await db.execute(
            select(UserDB).filter(UserDB.username == user_data.username)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # Check if email already exists
        result = await db.execute(
            select(UserDB).filter(UserDB.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already exists")
        
        # Validate role
        if user_data.role not in ["admin", "user"]:
            raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'user'")
        
        # Create new user
        new_user = UserDB(
            user_id=f"user_{int(datetime.utcnow().timestamp())}",
            username=user_data.username,
            email=user_data.email,
            password_hash=hash_password(user_data.password),
            role=user_data.role,
            is_active=True
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        logger.info(f"User {user_data.username} created by admin {admin.username}")
        
        return UserResponse(
            user_id=new_user.user_id,
            username=new_user.username,
            email=new_user.email,
            role=new_user.role,
            is_active=new_user.is_active,
            created_at=new_user.created_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Registration failed")


class UserSelfRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    display_name: str = ""


@router.post("/signup", response_model=Token)
async def self_register(user_data: UserSelfRegister, db: AsyncSession = Depends(get_session)):
    """
    Public self-registration endpoint.
    Creates a new 'user' role account and returns a JWT token immediately.
    """
    try:
        if len(user_data.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

        # Check if username already exists
        result = await db.execute(select(UserDB).filter(UserDB.username == user_data.username))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already taken")

        # Check if email already exists
        result = await db.execute(select(UserDB).filter(UserDB.email == user_data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        import uuid
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        new_user = UserDB(
            user_id=user_id,
            username=user_data.username,
            email=user_data.email,
            password_hash=hash_password(user_data.password),
            role="user",
            is_active=True,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        access_token = create_access_token(
            data={"sub": new_user.user_id, "username": new_user.username, "role": new_user.role}
        )
        logger.info(f"Self-registered user: {user_data.username}")
        return Token(
            access_token=access_token,
            token_type="bearer",
            user_id=new_user.user_id,
            username=new_user.username,
            role=new_user.role,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Self-registration error: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Registration failed")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserDB = Depends(get_current_user)):
    """Get current authenticated user information."""
    return UserResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat()
    )


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_session),
    admin: UserDB = Depends(require_admin)
):
    """List all users (admin only)."""
    try:
        result = await db.execute(select(UserDB).order_by(UserDB.created_at.desc()))
        users = result.scalars().all()
        
        return {
            "success": True,
            "users": [
                UserResponse(
                    user_id=u.user_id,
                    username=u.username,
                    email=u.email,
                    role=u.role,
                    is_active=u.is_active,
                    created_at=u.created_at.isoformat()
                )
                for u in users
            ]
        }
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role: str,
    db: AsyncSession = Depends(get_session),
    admin: UserDB = Depends(require_admin)
):
    """Update user role (admin only)."""
    try:
        if role not in ["admin", "user"]:
            raise HTTPException(status_code=400, detail="Invalid role")
        
        result = await db.execute(select(UserDB).filter(UserDB.user_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.role = role
        user.updated_at = datetime.utcnow()
        await db.commit()
        
        return {"success": True, "message": f"User role updated to {role}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update role: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_session),
    admin: UserDB = Depends(require_admin)
):
    """Delete user (admin only)."""
    try:
        result = await db.execute(select(UserDB).filter(UserDB.user_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.username == "admin":
            raise HTTPException(status_code=400, detail="Cannot delete admin account")
        
        await db.delete(user)
        await db.commit()
        
        return {"success": True, "message": "User deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete user: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
