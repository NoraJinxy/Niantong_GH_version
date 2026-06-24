"""
Purpose: Define Pydantic request/response schemas for the auth API area.
Related: app/routers/*, frontend API clients, docs_v2/2-50.
"""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict
