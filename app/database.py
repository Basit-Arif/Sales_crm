from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import Base
from app.config import Config
# Database configuration
DATABASE_URL = Config.SQLALCHEMY_DATABASE_URI
# Create the database engine

engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Create tables
def init_db():
    Base.metadata.create_all(bind=engine)

