from flask_sqlalchemy import SQLAlchemy
from datetime import datetime 
import pytz

def local_now():
    return datetime.now(pytz.timezone("Asia/Karachi"))

db = SQLAlchemy()