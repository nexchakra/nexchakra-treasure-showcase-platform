from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from app import models, schemas, auth
from app.database import engine, get_db
from app.auth import get_current_user

# Initialize FastAPI
app = FastAPI(title="NexChakra Jewelry API")

# Allow Frontend to talk to Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DEPENDENCIES ---

def get_current_admin(user: models.User = Depends(get_current_user)):
    """Helper to ensure the logged-in user is an admin."""
    if user.role != models.UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only admins can perform this action"
        )
    return user

# --- AUTH ROUTES ---

@app.post("/auth/register", response_model=schemas.UserOut)
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = models.User(
        name=user_data.name,
        email=user_data.email,
        phone=user_data.phone,
        password_hash=auth.hash_password(user_data.password),
        role=models.UserRole.customer
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/auth/login", response_model=schemas.Token)
def login(login_data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == login_data.email).first()
    
    if not user or not auth.verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    access_token = auth.create_access_token(data={"sub": user.email, "role": user.role})
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": user
    }

# --- CATEGORY ROUTES ---

@app.get("/categories", response_model=List[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).all()

@app.post("/categories", response_model=schemas.CategoryOut)
def create_category(
    category: schemas.CategoryCreate, 
    db: Session = Depends(get_db), 
    admin: models.User = Depends(get_current_admin)
):
    new_cat = models.Category(**category.model_dump())
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat

@app.put("/categories/{category_id}", response_model=schemas.CategoryOut)
def update_category(
    category_id: int, 
    updated_data: schemas.CategoryCreate, 
    db: Session = Depends(get_db), 
    admin: models.User = Depends(get_current_admin)
):
    cat_query = db.query(models.Category).filter(models.Category.id == category_id)
    category = cat_query.first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
        
    cat_query.update(updated_data.model_dump(), synchronize_session=False)
    db.commit()
    return cat_query.first()

# --- PRODUCT ROUTES ---

@app.get("/products", response_model=List[schemas.ProductOut])
def list_products(category_id: int = None, db: Session = Depends(get_db)):
    query = db.query(models.Product)
    if category_id:
        query = query.filter(models.Product.category_id == category_id)
    return query.all()

@app.post("/products", response_model=schemas.ProductOut)
def create_product(
    product: schemas.ProductCreate, 
    db: Session = Depends(get_db), 
    admin: models.User = Depends(get_current_admin)
):
    product_data = product.model_dump()
    if not product_data.get('slug'):
        product_data['slug'] = product_data['title'].lower().replace(" ", "-")

    new_product = models.Product(**product_data)
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product

@app.put("/products/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: int, 
    updated_data: schemas.ProductCreate, 
    db: Session = Depends(get_db), 
    admin: models.User = Depends(get_current_admin)
):
    product_query = db.query(models.Product).filter(models.Product.id == product_id)
    product = product_query.first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product_query.update(updated_data.model_dump(), synchronize_session=False)
    db.commit()
    return product_query.first()

@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int, 
    db: Session = Depends(get_db), 
    admin: models.User = Depends(get_current_admin)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    db.delete(product)
    db.commit()
    return None

@app.get("/")
def root():
    return {"status": "online", "message": "NexChakra Jewelry API is running"}