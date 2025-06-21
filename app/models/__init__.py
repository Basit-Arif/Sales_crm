from app.extension import db 
from datetime import datetime 
import pytz
from app.models.models import Meeting, Notification, SalesRep, ReminderLog  ,User

def local_now():
    return datetime.now(pytz.timezone("Asia/Karachi"))

