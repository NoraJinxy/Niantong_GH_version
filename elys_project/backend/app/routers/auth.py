"""
Purpose: Define FastAPI routes for the auth API area and translate HTTP requests into services/database calls.
Related: app/schemas/*, app/models/*, app/services/*, app/routers/auth.py, docs_v2/2-50.
"""

from datetime import datetime
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, LoginResponse, RefreshRequest
from app.utils.security import verify_password, create_access_token, decode_token

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None:
        raise exc
    user_id = payload.get("sub")
    if user_id is None:
        raise exc
    try:
        user_uuid = PyUUID(user_id)
    except ValueError:
        raise exc
    user = db.query(User).filter(User.id == user_uuid).first()
    if user is None:
        raise exc
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    return user


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()

    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="账号已被禁用")
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user.last_login_at = datetime.utcnow()
    db.commit()

    sub = str(user.id)
    roles = [r.code for r in user.roles]
    access_token = create_access_token(
        data={"sub": sub, "username": user.username, "roles": roles}
    )
    refresh_token = create_access_token(
        data={"sub": sub, "type": "refresh"}
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user.to_dict(),
    )


@router.post("/refresh", response_model=LoginResponse)
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(request.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="无效的刷新令牌")

    try:
        user_uuid = PyUUID(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="无效的刷新令牌")

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户无效")

    sub = str(user.id)
    roles = [r.code for r in user.roles]
    new_access = create_access_token(
        data={"sub": sub, "username": user.username, "roles": roles}
    )
    new_refresh = create_access_token(data={"sub": sub, "type": "refresh"})

    return LoginResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        user=user.to_dict(),
    )


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"user": current_user.to_dict()}
