from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from typing import List,Optional
from sqlalchemy import desc,func
from app import models, schemas, auth
from app.database import engine, get_db
from app.auth import get_current_user
from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

# Initialize FastAPI
app = FastAPI(title="NexChakra Jewelry API")

# Allow Frontend to talk to Backend (Updated for Vite/Local Dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
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
def list_products(
    category_id: Optional[int] = None, 
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    material: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Product)

    if category_id:
        query = query.filter(models.Product.category_id == category_id)
    if search:
        query = query.filter((models.Product.title.ilike(f"%{search}%")) | (models.Product.description.ilike(f"%{search}%")))
    if material:
        query = query.filter(models.Product.material.ilike(f"%{material}%"))
    if min_price is not None:
        query = query.filter(models.Product.price >= min_price)
    if max_price is not None:
        query = query.filter(models.Product.price <= max_price)

    # Sorting Logic 
    if sort_by == "price_asc":
        query = query.order_by(models.Product.price.asc())
    elif sort_by == "price_desc":
        query = query.order_by(models.Product.price.desc())
    elif sort_by == "newest":
        query = query.order_by(desc(models.Product.id))
    
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

# --- CART HELPER ---

def get_or_create_cart(db: Session, user_id: int):
    cart = db.query(models.Cart).filter(models.Cart.user_id == user_id).first()
    if not cart:
        cart = models.Cart(user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart

# --- CART ROUTES ---

@app.get("/cart", response_model=schemas.CartOut)
def get_user_cart(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    cart = get_or_create_cart(db, current_user.id)
    
    # Calculate Total Price (Optional: can also be done on frontend)
    total = 0
    for item in cart.items:
        price = item.product.discount_price if item.product.discount_price else item.product.price
        total += float(price) * item.quantity
    
    cart.total_price = total
    return cart

@app.post("/cart/items", response_model=schemas.CartItemOut)
def add_to_cart(
    item_data: schemas.CartItemCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    cart = get_or_create_cart(db, current_user.id)
    
    # 1. Check if product exists and has stock
    product = db.query(models.Product).filter(models.Product.id == item_data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.stock < item_data.quantity:
        raise HTTPException(status_code=400, detail="Not enough stock available")

    # 2. Check if item is already in the cart
    existing_item = db.query(models.CartItem).filter(
        models.CartItem.cart_id == cart.id,
        models.CartItem.product_id == item_data.product_id
    ).first()

    if existing_item:
        # Update quantity
        existing_item.quantity += item_data.quantity
        db.commit()
        db.refresh(existing_item)
        return existing_item
    else:
        # Create new cart item
        new_item = models.CartItem(
            cart_id=cart.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            variant_id=item_data.variant_id
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return new_item

@app.delete("/cart/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_cart(
    item_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    cart = get_or_create_cart(db, current_user.id)
    item = db.query(models.CartItem).filter(
        models.CartItem.id == item_id, 
        models.CartItem.cart_id == cart.id
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in your cart")
        
    db.delete(item)
    db.commit()
    return None

# --- ORDER ROUTES ---
@app.post("/orders", response_model=schemas.OrderOut)
async def create_order(
    address_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    cart = db.query(models.Cart).filter(models.Cart.user_id == current_user.id).first()
    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    total_amount = 0
    order_items_to_create = []
    
    for cart_item in cart.items:
        product = cart_item.product
        if product.stock < cart_item.quantity:
            raise HTTPException(status_code=400, detail=f"Not enough stock for {product.title}")
        
        item_price = product.discount_price if product.discount_price else product.price
        total_amount += float(item_price) * cart_item.quantity
        order_items_to_create.append({"product_id": product.id, "quantity": cart_item.quantity, "price": item_price, "variant_id": cart_item.variant_id})

    new_order = models.Order(user_id=current_user.id, address_id=address_id, total_amount=total_amount, status="pending", payment_status="pending")
    db.add(new_order)
    db.flush() 

    for item_data in order_items_to_create:
        order_item = models.OrderItem(order_id=new_order.id, **item_data)
        db.add(order_item)
        product = db.query(models.Product).filter(models.Product.id == item_data["product_id"]).first()
        product.stock -= item_data["quantity"]

    db.query(models.CartItem).filter(models.CartItem.cart_id == cart.id).delete()
    db.commit()
    db.refresh(new_order)

    # BROADCAST ALERT (Must happen before return!)
    await manager.broadcast({
        "event": "NEW_ORDER",
        "order_id": new_order.id,
        "customer": current_user.name,
        "amount": total_amount
    })

    return new_order
    

@app.get("/orders", response_model=List[schemas.OrderOut])
def get_my_orders(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Order).filter(models.Order.user_id == current_user.id).all()

# --- ADDRESS ROUTES ---

@app.post("/addresses", response_model=schemas.AddressOut)
def add_address(
    address: schemas.AddressCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    # If this is set as default, unset other defaults for this user
    if address.is_default:
        db.query(models.Address).filter(
            models.Address.user_id == current_user.id
        ).update({"is_default": False})

    new_address = models.Address(**address.model_dump(), user_id=current_user.id)
    db.add(new_address)
    db.commit()
    db.refresh(new_address)
    return new_address

@app.get("/addresses", response_model=List[schemas.AddressOut])
def get_my_addresses(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    return db.query(models.Address).filter(models.Address.user_id == current_user.id).all()

@app.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(
    address_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    address = db.query(models.Address).filter(
        models.Address.id == address_id, 
        models.Address.user_id == current_user.id
    ).first()
    
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
        
    db.delete(address)
    db.commit()
    return None

@app.get("/admin/analytics/dashboard")
def get_admin_dashboard_stats(
    db: Session = Depends(get_db), 
    admin: models.User = Depends(get_current_admin)
):
    # 1. Total Revenue
    total_revenue = db.query(func.sum(models.Order.total_amount))\
        .filter(models.Order.status != "cancelled")\
        .scalar() or 0

    # 2. Total Orders Count
    total_orders = db.query(models.Order).count()

    # 3. Top Selling Products (Sorted by quantity sold)
    top_products = db.query(
        models.Product.title,
        func.sum(models.OrderItem.quantity).label("total_sold")
    )\
    .join(models.OrderItem)\
    .group_by(models.Product.id)\
    .order_by(desc("total_sold"))\
    .limit(5)\
    .all()

    # Format top products for the frontend
    top_products_list = [{"name": p[0], "sold": p[1]} for p in top_products]

    return {
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "top_selling_products": top_products_list
    }
    
# --- ADMIN ORDER MANAGEMENT ---

@app.get("/admin/orders", response_model=List[schemas.OrderOut])
def get_all_orders(
    status: Optional[str] = None, 
    db: Session = Depends(get_db), 
    admin: models.User = Depends(get_current_admin)
):
    """Allows Admin to see every order in the system, optionally filtered by status."""
    query = db.query(models.Order)
    if status:
        query = query.filter(models.Order.status == status)
    return query.all()

@app.patch("/admin/orders/{order_id}/status", response_model=schemas.OrderOut)
def update_order_status(
    order_id: int, 
    new_status: str, # e.g., "shipped", "delivered", "cancelled"
    db: Session = Depends(get_db), 
    admin: models.User = Depends(get_current_admin)
):
    """Updates the status of a specific order."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order.status = new_status
    db.commit()
    db.refresh(order)
    return order

# --- WISHLIST ROUTES ---

@app.post("/wishlist/{product_id}", status_code=status.HTTP_200_OK)
def toggle_wishlist(
    product_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """Adds or removes a product from the user's wishlist."""
    # Check if product exists
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check if it's already in the wishlist
    wishlist_item = db.query(models.Wishlist).filter(
        models.Wishlist.user_id == current_user.id,
        models.Wishlist.product_id == product_id
    ).first()

    if wishlist_item:
        db.delete(wishlist_item)
        db.commit()
        return {"message": "Removed from wishlist"}
    
    new_item = models.Wishlist(user_id=current_user.id, product_id=product_id)
    db.add(new_item)
    db.commit()
    return {"message": "Added to wishlist"}

@app.get("/wishlist", response_model=List[schemas.ProductOut])
def get_my_wishlist(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """Returns all products in the user's wishlist."""
    # We join with Product to return the actual product details
    items = db.query(models.Product)\
        .join(models.Wishlist)\
        .filter(models.Wishlist.user_id == current_user.id)\
        .all()
    return items


@app.websocket("/ws/admin/notifications")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep the connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)