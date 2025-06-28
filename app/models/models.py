from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func,Text
from flask_sqlalchemy import SQLAlchemy
from app.models import db

from datetime import datetime
import pytz

def local_now():
    return datetime.now(pytz.timezone("Asia/Karachi"))

class Company(db.Model):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    messenger_page_id = Column(String(100), unique=True, nullable=False)
    instagram_page_id = Column(String(100), unique=True, nullable=True)
    created_at = Column(DateTime, default=local_now)
    messenger_access_token = db.Column(db.String(512))
    instagram_access_token = db.Column(db.String(512))

    sales_reps = db.relationship("SalesRep", back_populates="company")


class User(db.Model):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)  # hashed password
    is_admin = Column(Boolean, default=False)
    email = Column(db.String(120), unique=True, nullable=True)

    sales_rep = db.relationship("SalesRep", back_populates="user", uselist=False)


class SalesRep(db.Model):
    __tablename__ = "sales_reps"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True)
    name = Column(String(100))
    phone_number = Column(String(20), nullable=True)  # WhatsApp number
    active = Column(Boolean, default=True)
    status = Column(String(50), default="active")  # active, on_leave, resigned, terminated
    status_updated_at = Column(DateTime, default=local_now, onupdate=local_now)
    left_reason = Column(String(255), nullable=True)
    joined_at = Column(DateTime, default=local_now)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    company = db.relationship("Company", back_populates="sales_reps")
    user = db.relationship("User", back_populates="sales_rep")
    leads = db.relationship("Lead", back_populates="sales_rep")
    timezone = Column(String(50), default="Asia/Karachi")


class Lead(db.Model):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(20))  # 'messenger' or 'instagram'
    external_user_id = Column(String(100), unique=True, index=True)  # Messenger or Instagram user ID
    name = Column(String(100))
    message = Column(String(255))
    sales_rep_id = Column(Integer, ForeignKey("sales_reps.id"))
    ad_repr = Column(String(100), nullable=True)
    assigned_at = Column(DateTime, default=local_now)
    last_active_at = Column(DateTime, default=local_now, onupdate=local_now)
    status = Column(String(50), default="active")
    is_admin_override = Column(Boolean, default=False)

    sales_rep = db.relationship("SalesRep", back_populates="leads")


class LeadMessage(db.Model):
    __tablename__ = "lead_messages"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    sender = Column(String(50))  # 'rep' or 'user'
    content = Column(String(1000))
    message_type = Column(String(50), default="text")  # e.g., text, image, file
    direction = Column(String(10), default="out")  # out (sent by rep), in (received from user)
    status = Column(String(20), default="sent")  # sent, delivered, read
    timestamp = Column(DateTime, default=local_now, nullable=False)
    read_at = Column(DateTime, nullable=True)
    is_read = Column(Boolean, default=False)
    platform_message_id = Column(String(255), nullable=True)

    lead = db.relationship("Lead", backref="messages")

class LeadStatusHistory(db.Model):
    __tablename__ = "lead_status_history"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    status = Column(String(50))  # active, converted, closed
    changed_by = Column(Integer, ForeignKey("sales_reps.id"))  # or Admin ID
    changed_at = Column(DateTime, default=local_now)

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = Column(Integer, primary_key=True)
    sender_name = Column(String(100), nullable=False)
    platform = Column(String(50), nullable=False)  # Messenger, Instagram
    lead_id = Column(Integer, ForeignKey('leads.id'))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=local_now)

class Meeting(db.Model):
    __tablename__ = 'meetings'

    id = Column(Integer, primary_key=True)
    sales_rep_id = Column(Integer, ForeignKey('sales_reps.id'), nullable=False)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=False)

    meeting_time_utc = Column(DateTime, nullable=False)       # Always store in UTC
    client_timezone = Column(String(50), nullable=False)       # e.g., 'US/Pacific'
    rep_timezone = Column(String(50), nullable=True)

    
    original_message = Column(String(100), nullable=False)  # Full message that triggered the meeting detection
    detected_date_string = Column(String(100))       # Extracted date phrase like "next Friday"
    detected_time_string = Column(String(100))       # Extracted time phrase like "5pm"
    status = Column(String(20), default="pending")   # pending / confirmed / cancelled / rescheduled
    notes = Column(String(200))                             # Optional field for rep’s update post meeting
    created_at = Column(DateTime, default=local_now)
    updated_at = Column(DateTime, default=local_now, onupdate=local_now)

    # Optional relationships
    sales_rep = db.relationship("SalesRep", backref="meetings")
    lead = db.relationship("Lead", backref="meetings")


class LeadComment(db.Model):
    __tablename__ = "lead_comments"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    content = Column(Text, nullable=False)  # GPT summary
    summary_date = Column(DateTime, nullable=False)  # E.g., 2024-08-27
    generated_by = Column(String(20), default="gpt")  # or "gpt","user","admin"
    created_at = Column(DateTime, default=local_now)


    lead = db.relationship("Lead", backref="comments")



class ReminderPurpose(db.Model):
    __tablename__ = "reminder_purpose"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)



class ReminderLog(db.Model):
    __tablename__ = "reminder_log"

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    purpose_id = db.Column(db.Integer, db.ForeignKey("reminder_purpose.id"), nullable=False)
    scheduled_for = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="pending")
    retry_count = db.Column(db.Integer, default=0)

    lead = db.relationship("Lead", backref="reminder_logs")
    purpose = db.relationship("ReminderPurpose", backref="reminders")