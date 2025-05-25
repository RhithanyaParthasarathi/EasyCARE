from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base  # Import your Base

DATABASE_URL = "sqlite:///./site.db"  # SQLite file

engine = create_engine(DATABASE_URL, echo=True) # Make true

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
    # Function to create the tables
def create_tables():
    Base.metadata.create_all(bind=engine)
create_tables()