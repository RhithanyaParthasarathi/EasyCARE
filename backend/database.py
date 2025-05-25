# backend/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base # Ensure this is your Base from models.py and models.py is complete

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./site.db")

print(f"Attempting to connect to database (details redacted for log): {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    print("Using SQLite database engine for local development.")
else:
    engine = create_engine(DATABASE_URL)
    print(f"Using non-SQLite database engine (PostgreSQL expected for {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}).")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_db_tables():
    print("Attempting to create database tables if they don't exist...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Base.metadata.create_all() executed successfully.")
    except Exception as e:
        print(f"Error during Base.metadata.create_all(): {e}")
        # You might want to raise this or handle it more robustly in production
        # For now, just printing the error.

# Call this function when the application starts (e.g., when database.py is imported)
# This ensures tables are created if connected to a new, empty database.
if not DATABASE_URL.startswith("sqlite"): # Only run for cloud DB on app startup
    print("Running create_db_tables for cloud database...")
    create_db_tables()
elif os.environ.get("CREATE_LOCAL_DB_TABLES") == "true": # Or a flag for local
    print("Running create_db_tables for local SQLite database...")
    create_db_tables()