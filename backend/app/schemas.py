from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from .models import UserRole

# --- AUTH SCHEMAS ---

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

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

# --- CATEGORY SCHEMAS ---

class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    slug: Optional[str] = None
    image: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryOut(CategoryBase):
    id: int
    
    class Config:
        from_attributes = True

# --- PRODUCT SCHEMAS ---

class ProductBase(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    discount_price: Optional[float] = None
    category_id: int
    stock: int = 0
    material: Optional[str] = None
    weight: Optional[float] = None
    image_url: Optional[str] = None
    sku: Optional[str] = None
    is_limited: bool = False
    is_active: bool = True

class ProductCreate(ProductBase):
    slug: Optional[str] = None

class ProductOut(ProductBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True