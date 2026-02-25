from pydantic import BaseModel, EmailStr
from typing import Optional
from .models import UserRole

# Data required for Registration
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None

# Data required for Login
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# Data returned to Frontend (hiding the password)
class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut