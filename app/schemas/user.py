from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.user import UserRole


class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str
    role: UserRole = UserRole.CLIENT
    phone: Optional[str] = None
    city: Optional[str] = None
    bar_number: Optional[str] = None
    specialization: Optional[str] = None
    preferred_language: str = "en"


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    phone: Optional[str] = None
    city: Optional[str] = None
    specialization: Optional[str] = None
    preferred_language: str = "en"
    is_active: bool = True

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
