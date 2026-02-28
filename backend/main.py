from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session, joinedload
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from sqlalchemy import desc, func
import uuid

from app import models, schemas, auth
from app.database import engine, get_db
from app.auth import get_current_user

# --- WEBSOCKET MANAGER ---
class ConnectionManager:
    def __init__(self):
        # Stores all active websocket connections for real-time updates
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Sends a JSON message to everyone connected (Broadcast)."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                # Silently handle stale or broken connections
                pass

manager = ConnectionManager()

# Initialize FastAPI
app = FastAPI(title="NexChakra Premium Jewelry API")

# Allow Frontend to talk to Backend (Vite/Local Dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173","https://jewellery-zo7x.vercel.app","https://jewellery-zo7x.vercel.app/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- HELPERS & DEPENDENCIES ---
def get_current_admin(user: models.User = Depends(get_current_user)):
    """Ensures the logged-in user has admin privileges."""
    if user.role != models.UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only admins can perform this action"
        )
    return user

def generate_sku():
    """Auto-generates a unique SKU for new products."""
    return "NX-" + uuid.uuid4().hex[:8].upper()

def get_or_create_cart(db: Session, user_id: int):
    """Retrieves an existing cart or creates a new one for a user."""
    cart = db.query(models.Cart).filter(models.Cart.user_id == user_id).first()
    if not cart:
        cart = models.Cart(user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart

# --- AUTH ROUTES ---
@app.post("/auth/register", response_model=schemas.UserOut)
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == user_data.email).first():
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
    return {"access_token": access_token, "token_type": "bearer", "user": user}

# --- CATEGORY ROUTES ---
@app.get("/categories", response_model=List[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).all()

@app.post("/categories", response_model=schemas.CategoryOut)
def create_category(category: schemas.CategoryCreate, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    new_cat = models.Category(**category.model_dump())
    db.add(new_cat); db.commit(); db.refresh(new_cat)
    return new_cat

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
    if category_id: query = query.filter(models.Product.category_id == category_id)
    if search: query = query.filter((models.Product.title.ilike(f"%{search}%")) | (models.Product.description.ilike(f"%{search}%")))
    if material: query = query.filter(models.Product.material.ilike(f"%{material}%"))
    if min_price is not None: query = query.filter(models.Product.price >= min_price)
    if max_price is not None: query = query.filter(models.Product.price <= max_price)

    if sort_by == "price_asc": query = query.order_by(models.Product.price.asc())
    elif sort_by == "price_desc": query = query.order_by(models.Product.price.desc())
    else: query = query.order_by(desc(models.Product.id))
    
    return query.all()

@app.post("/products", response_model=schemas.ProductOut)
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    data = product.model_dump()
    if not data.get("slug"): data["slug"] = data["title"].lower().replace(" ", "-")
    if not data.get("sku"): data["sku"] = generate_sku()
    new_product = models.Product(**data)
    db.add(new_product); db.commit(); db.refresh(new_product)
    return new_product

# --- CART ROUTES ---
@app.get("/cart", response_model=schemas.CartOut)
def get_user_cart(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    cart = get_or_create_cart(db, current_user.id)
    total = 0
    for item in cart.items:
        price = item.product.discount_price or item.product.price
        total += float(price) * item.quantity
    cart.total_price = total
    return cart

@app.post("/cart/items", response_model=schemas.CartItemOut)
def add_to_cart(item_data: schemas.CartItemCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    cart = get_or_create_cart(db, current_user.id)
    product = db.query(models.Product).filter(models.Product.id == item_data.product_id).first()
    
    if not product or product.stock < item_data.quantity:
        raise HTTPException(status_code=400, detail="Stock low or product unavailable")

    existing = db.query(models.CartItem).filter(models.CartItem.cart_id == cart.id, models.CartItem.product_id == item_data.product_id).first()
    if existing:
        existing.quantity += item_data.quantity
    else:
        db.add(models.CartItem(cart_id=cart.id, **item_data.model_dump()))
    
    db.commit()
    # Reload with joined product info for frontend display
    return db.query(models.CartItem).options(joinedload(models.CartItem.product)).filter(
        models.CartItem.cart_id == cart.id, models.CartItem.product_id == item_data.product_id
    ).first()

@app.patch("/cart/items/{item_id}", response_model=schemas.CartItemOut)
def update_cart_quantity(item_id: int, quantity: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    cart = get_or_create_cart(db, current_user.id)
    item = db.query(models.CartItem).filter(models.CartItem.id == item_id, models.CartItem.cart_id == cart.id).first()
    if not item: raise HTTPException(status_code=404, detail="Item not found")
    
    if quantity <= 0:
        db.delete(item); db.commit(); raise HTTPException(status_code=200, detail="Item removed")
    
    product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
    if quantity > product.stock:
        raise HTTPException(status_code=400, detail=f"Only {product.stock} items available")

    item.quantity = quantity
    db.commit()
    return db.query(models.CartItem).options(joinedload(models.CartItem.product)).filter(models.CartItem.id == item_id).first()

# --- ORDER & REAL-TIME SYNC ---
@app.post("/orders", response_model=schemas.OrderOut)
async def create_order(address_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    cart = db.query(models.Cart).options(joinedload(models.Cart.items).joinedload(models.CartItem.product)).filter(models.Cart.user_id == current_user.id).first()
    
    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    total_amount = 0
    order_items_data = []
    
    for item in cart.items:
        # with_for_update prevents race conditions (Live Stock Sync)
        prod = db.query(models.Product).with_for_update().filter(models.Product.id == item.product_id).first()
        if prod.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Stock low for {prod.title}")
        
        price = prod.discount_price or prod.price
        total_amount += float(price) * item.quantity
        order_items_data.append({"prod": prod, "qty": item.quantity, "price": price, "vid": item.variant_id})

    new_order = models.Order(user_id=current_user.id, address_id=address_id, total_amount=total_amount, status="pending")
    db.add(new_order); db.flush()

    for entry in order_items_data:
        db.add(models.OrderItem(order_id=new_order.id, product_id=entry["prod"].id, quantity=entry["qty"], price=entry["price"], variant_id=entry["vid"]))
        entry["prod"].stock -= entry["qty"]
        
        # LIVE STOCK BROADCAST: Updates inventory instantly for all users
        await manager.broadcast({"event": "STOCK_UPDATE", "product_id": entry["prod"].id, "new_stock": entry["prod"].stock})
        
        # LOW STOCK ALERT: Triggers indicator if stock <= 5
        if entry["prod"].stock <= 5:
            await manager.broadcast({"event": "LOW_STOCK_WARNING", "product": entry["prod"].title, "remaining": entry["prod"].stock})

    db.query(models.CartItem).filter(models.CartItem.cart_id == cart.id).delete()
    db.commit(); db.refresh(new_order)
    
    # ADMIN NOTIFICATION
    await manager.broadcast({"event": "NEW_ORDER", "order_id": new_order.id, "customer": current_user.name, "amount": total_amount})
    return new_order

@app.patch("/orders/{order_id}/cancel", response_model=schemas.OrderOut)
async def cancel_order(
    order_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    # 1. Fetch order with items
    order = db.query(models.Order).options(joinedload(models.Order.items)).filter(
        models.Order.id == order_id
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # 2. Security: Only the owner or an admin can cancel
    if order.user_id != current_user.id and current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this order")

    # 3. Logic: Only allow cancellation of 'pending' orders
    if order.status.lower() != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot cancel order with status: {order.status}")

    try:
        # 4. RESTOCK: Return items to inventory
        for item in order.items:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            if product:
                product.stock += item.quantity
                # Notify everyone that stock increased
                await manager.broadcast({
                    "event": "STOCK_UPDATE", 
                    "product_id": product.id, 
                    "new_stock": product.stock
                })

        # 5. Update Status
        order.status = "cancelled"
        db.commit()
        db.refresh(order)

        # 6. Notify Admin of Cancellation
        await manager.broadcast({
            "event": "ORDER_CANCELLED", 
            "order_id": order.id, 
            "customer": current_user.name
        })

        return order

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Cancellation failed: {str(e)}")
    
# --- ADMIN ENDPOINTS ---
@app.get("/admin/analytics/dashboard")
def get_dashboard_stats(db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    rev = db.query(func.sum(models.Order.total_amount)).filter(models.Order.status != "cancelled").scalar() or 0
    tops = db.query(models.Product.title, func.sum(models.OrderItem.quantity).label("sold")).join(models.OrderItem).group_by(models.Product.id).order_by(desc("sold")).limit(5).all()
    
    return {
        "total_revenue": rev,
        "total_orders": db.query(models.Order).count(),
        "top_selling_products": [{"name": p[0], "sold": p[1]} for p in tops]
    }

@app.get("/admin/users", response_model=List[schemas.UserOut])
def get_all_customers(db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    """Deduplicated user route: Returns all registered customers sorted by newest."""
    return db.query(models.User).filter(models.User.role == models.UserRole.customer).order_by(models.User.id.desc()).all()

@app.get("/admin/carts")
def get_all_active_carts(db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    """Returns every active user cart with detailed product nesting."""
    return db.query(models.Cart).options(joinedload(models.Cart.user), joinedload(models.Cart.items).joinedload(models.CartItem.product)).all()

@app.get("/admin/orders")
def get_all_orders(db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    """Returns all orders globally for admin tracking."""
    return db.query(models.Order).options(joinedload(models.Order.user), joinedload(models.Order.items).joinedload(models.OrderItem.product)).order_by(models.Order.id.desc()).all()

# --- WISHLIST & ADDRESSES ---
@app.post("/wishlist/{product_id}")
def toggle_wishlist(product_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    item = db.query(models.Wishlist).filter(models.Wishlist.user_id == current_user.id, models.Wishlist.product_id == product_id).first()
    if item:
        db.delete(item); db.commit()
        return {"message": "Removed from wishlist"}
    db.add(models.Wishlist(user_id=current_user.id, product_id=product_id))
    db.commit()
    return {"message": "Added to wishlist"}

@app.get("/addresses", response_model=List[schemas.AddressOut])
def get_my_addresses(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Address).filter(models.Address.user_id == current_user.id).all()

# --- WEBSOCKET ENDPOINT ---
@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keeps the socket open to receive data pushes from server
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
def root():
    return {"status": "online", "message": "NexChakra Jewelry API Active"}

