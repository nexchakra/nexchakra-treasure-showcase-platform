from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey, Numeric, Text, Enum
from sqlalchemy.sql import func
from .database import Base
import enum

class UserRole(str, enum.Enum):
    admin = "admin"
    customer = "customer"

class UserStatus(str, enum.Enum):
    active = "active"
    blocked = "blocked"

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True) # Optional for registration
    password_hash = Column(Text, nullable=False)
    
    # Using the Enum classes defined above for strict type safety
    role = Column(
        Enum(UserRole, name="user_roles"), 
        default=UserRole.customer,
        nullable=False
    )
    status = Column(
        Enum(UserStatus, name="user_status"), 
        default=UserStatus.active,
        nullable=False
    )
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
class Address(Base):
    __tablename__ = "addresses"
    id = Column(BigInteger, primary_key=True) # [cite: 9]
    user_id = Column(BigInteger, ForeignKey("users.id")) # [cite: 9]
    full_address = Column(Text, nullable=False) # [cite: 9]
    city = Column(String) # [cite: 9]
    state = Column(String) # [cite: 9]
    pincode = Column(String) # [cite: 9]
    country = Column(String) # [cite: 9]
    is_default = Column(Boolean, default=False) # [cite: 9]
    
class Category(Base):
    __tablename__ = "categories"
    id = Column(BigInteger, primary_key=True) # [cite: 12]
    name = Column(String, nullable=False) # [cite: 12]
    slug = Column(String, unique=True) # [cite: 13]
    parent_id = Column(BigInteger, ForeignKey("categories.id"), nullable=True) # [cite: 13]
    description = Column(Text) # [cite: 13]
    image = Column(Text) # [cite: 13]

class Product(Base):
    __tablename__ = "products"
    id = Column(BigInteger, primary_key=True) # [cite: 21]
    category_id = Column(BigInteger, ForeignKey("categories.id")) # [cite: 21]
    title = Column(String, nullable=False) # [cite: 21]
    description = Column(Text) # [cite: 21]
    price = Column(Numeric(10, 2), nullable=False) # [cite: 21]
    discount_price = Column(Numeric(10, 2)) # [cite: 21]
    material = Column(String) # [cite: 21]
    weight = Column(Numeric(10, 2)) # [cite: 21]
    stock = Column(Integer, default=0) # [cite: 21]
    sku = Column(String, unique=True) # [cite: 21]
    is_limited = Column(Boolean, default=False) # [cite: 21]
    is_active = Column(Boolean, default=True) # [cite: 21]
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # [cite: 21]
    
class ProductImage(Base):
    __tablename__ = "product_images"
    id = Column(BigInteger, primary_key=True) # [cite: 24]
    product_id = Column(BigInteger, ForeignKey("products.id")) # [cite: 24]
    image_url = Column(Text, nullable=False) # [cite: 24]
    is_primary = Column(Boolean, default=False) # [cite: 24]

class ProductVariant(Base):
    __tablename__ = "product_variants"
    id = Column(BigInteger, primary_key=True) # [cite: 27]
    product_id = Column(BigInteger, ForeignKey("products.id")) # [cite: 27]
    variant_name = Column(String) # e.g., Size [cite: 27]
    variant_value = Column(String) # e.g., 7 [cite: 27]
    price = Column(Numeric(10, 2)) # [cite: 27]
    stock = Column(Integer) # [cite: 27]

class Attribute(Base):
    __tablename__ = "attributes"
    id = Column(Integer, primary_key=True) # [cite: 30]
    name = Column(String, nullable=False) # Material, Stone, etc. [cite: 30]

class ProductAttribute(Base):
    __tablename__ = "product_attributes"
    id = Column(BigInteger, primary_key=True) # [cite: 32]
    product_id = Column(BigInteger, ForeignKey("products.id")) # [cite: 32]
    attribute_id = Column(Integer, ForeignKey("attributes.id")) # [cite: 32]
    value = Column(String) # [cite: 32]
    
class Cart(Base):
    __tablename__ = "carts"
    id = Column(BigInteger, primary_key=True) # [cite: 35]
    user_id = Column(BigInteger, ForeignKey("users.id")) # [cite: 35]
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # [cite: 35]

class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(BigInteger, primary_key=True) # [cite: 37]
    cart_id = Column(BigInteger, ForeignKey("carts.id")) # [cite: 37]
    product_id = Column(BigInteger, ForeignKey("products.id")) # [cite: 38]
    variant_id = Column(BigInteger, ForeignKey("product_variants.id"), nullable=True) # [cite: 38]
    quantity = Column(Integer, default=1) # [cite: 38]

class Wishlist(Base):
    __tablename__ = "wishlists"
    id = Column(BigInteger, primary_key=True) # [cite: 40]
    user_id = Column(BigInteger, ForeignKey("users.id")) # [cite: 40]
    product_id = Column(BigInteger, ForeignKey("products.id")) # [cite: 40]
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # [cite: 40]
    
class Order(Base):
    __tablename__ = "orders"
    id = Column(BigInteger, primary_key=True) # [cite: 43]
    user_id = Column(BigInteger, ForeignKey("users.id")) # [cite: 43]
    address_id = Column(BigInteger, ForeignKey("addresses.id")) # [cite: 43]
    total_amount = Column(Numeric(10, 2)) # [cite: 43]
    status = Column(Enum('pending', 'paid', 'shipped', 'delivered', 'cancelled', name='order_status')) # [cite: 43]
    payment_status = Column(Enum('pending', 'success', 'failed', name='payment_status')) # [cite: 43]
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # [cite: 43]

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(BigInteger, primary_key=True) # [cite: 45]
    order_id = Column(BigInteger, ForeignKey("orders.id")) # [cite: 45]
    product_id = Column(BigInteger, ForeignKey("products.id")) # [cite: 45]
    variant_id = Column(BigInteger, ForeignKey("product_variants.id")) # [cite: 45]
    price = Column(Numeric(10, 2)) # [cite: 45]
    quantity = Column(Integer) # [cite: 45]

class Payment(Base):
    __tablename__ = "payments"
    id = Column(BigInteger, primary_key=True) # [cite: 47]
    order_id = Column(BigInteger, ForeignKey("orders.id")) # [cite: 47]
    payment_method = Column(String) # [cite: 47]
    transaction_id = Column(String) # [cite: 47]
    amount = Column(Numeric(10, 2)) # [cite: 47]
    status = Column(String) # [cite: 47]
    paid_at = Column(DateTime(timezone=True), server_default=func.now()) # [cite: 49]
    
class Review(Base):
    __tablename__ = "reviews"
    id = Column(BigInteger, primary_key=True) # [cite: 52]
    user_id = Column(BigInteger, ForeignKey("users.id")) # [cite: 52]
    product_id = Column(BigInteger, ForeignKey("products.id")) # [cite: 52]
    rating = Column(Integer) # [cite: 52]
    comment = Column(Text) # [cite: 52]
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # [cite: 52]

class StockLog(Base):
    __tablename__ = "stock_logs"
    id = Column(BigInteger, primary_key=True) # [cite: 56]
    product_id = Column(BigInteger, ForeignKey("products.id")) # [cite: 56]
    change_type = Column(Enum('order', 'admin_update', 'return', name='change_type')) # [cite: 56]
    quantity_change = Column(Integer) # [cite: 56]
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # [cite: 56]

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(BigInteger, primary_key=True) # [cite: 58]
    user_id = Column(BigInteger, ForeignKey("users.id")) # Admin [cite: 58]
    title = Column(String) # [cite: 58]
    message = Column(Text) # [cite: 58]
    is_read = Column(Boolean, default=False) # [cite: 58]
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # [cite: 58]