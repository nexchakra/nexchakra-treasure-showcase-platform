# init_db.py
from app.database import engine, Base
from app.models import User, Product  # Import all models here

def create_tables():
    print("Connecting to Neon...")
    try:
        # This command creates the tables in the DB if they don't exist
        Base.metadata.create_all(bind=engine)
        print("✅ Success! Tables created in Neon.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    create_tables()