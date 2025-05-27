from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Config
from flask_sqlalchemy import SQLAlchemy
# Database configuration
DATABASE_URL = Config.SQLALCHEMY_DATABASE_URI
db = SQLAlchemy()

# Create tables
def init_db(app):
    app.config.from_object(Config)
    db.init_app(app)
