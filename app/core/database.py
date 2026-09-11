#SQLAlchemy engine + session factory
#SQLAlchemy ORM models (one file per entity)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from app.core.config import settings
from dotenv import load_dotenv
import os

load_dotenv()

#declare the database URL and create the engine
SQLALCHEMY_DATABASE_URL = str(settings.DATABASE_URL)
engine = create_engine(SQLALCHEMY_DATABASE_URL)

#create a session factory for the database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

#declare the base class for the ORM models
Base = declarative_base()

#dependency injection for database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()