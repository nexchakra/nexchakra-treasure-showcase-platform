from app.database import SessionLocal
from app.models import User, UserRole, UserStatus # Import the Enums
from app.auth import hash_password

def create_admin():
    db = SessionLocal()
    
    admin_email = "admin@nexchakra.com"
    
    admin_exists = db.query(User).filter(User.email == admin_email).first()
    
    if not admin_exists:
        admin = User(
            name="Super Admin",
            email=admin_email,
            phone="0000000000", 
            password_hash=hash_password("Admin@123"), 
            role=UserRole.admin,    
            status=UserStatus.active 
        )
        db.add(admin)
        db.commit()
        print(f"✅ Admin created with Email: {admin_email} and Password: Admin@123")
    else:
        print("⚠️ Admin already exists.")
    db.close()

if __name__ == "__main__":
    create_admin()