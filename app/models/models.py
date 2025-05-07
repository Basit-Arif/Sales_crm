from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime


Base = declarative_base()


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    messenger_page_id = Column(String(100), unique=True, nullable=False)
    instagram_page_id = Column(String(100), unique=True, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    sales_reps = relationship("SalesRep", back_populates="company")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)  # hashed password
    is_admin = Column(Boolean, default=False)

    sales_rep = relationship("SalesRep", back_populates="user", uselist=False)


class SalesRep(Base):
    __tablename__ = "sales_reps"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True)
    name = Column(String(100))
    phone_number = Column(String(20), nullable=True)  # WhatsApp number
    active = Column(Boolean, default=True)
    status = Column(String(50), default="active")  # active, on_leave, resigned, terminated
    status_updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    left_reason = Column(String(255), nullable=True)
    joined_at = Column(DateTime, server_default=func.now())
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    company = relationship("Company", back_populates="sales_reps")
    user = relationship("User", back_populates="sales_rep")
    leads = relationship("Lead", back_populates="sales_rep")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(20))  # 'messenger' or 'instagram'
    external_user_id = Column(String(100), unique=True, index=True)  # Messenger or Instagram user ID
    name = Column(String(100))
    message = Column(String(255))
    sales_rep_id = Column(Integer, ForeignKey("sales_reps.id"))
    ad_repr = Column(String(100), nullable=True)
    assigned_at = Column(DateTime, server_default=func.now())
    last_active_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    status = Column(String(50), default="active")

    sales_rep = relationship("SalesRep", back_populates="leads")


class LeadMessage(Base):
    __tablename__ = "lead_messages"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    sender = Column(String(50))  # 'rep' or 'user'
    content = Column(String(1000))
    message_type = Column(String(50), default="text")  # e.g., text, image, file
    direction = Column(String(10), default="out")  # out (sent by rep), in (received from user)
    status = Column(String(20), default="sent")  # sent, delivered, read
    timestamp = Column(DateTime, default=func.now())
    read_at = Column(DateTime, nullable=True)
    is_read = Column(Boolean, default=False)
    platform_message_id = Column(String(255), nullable=True)

    lead = relationship("Lead", backref="messages")

class LeadStatusHistory(Base):
    __tablename__ = "lead_status_history"

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    status = Column(String(50))  # active, converted, closed
    changed_by = Column(Integer, ForeignKey("sales_reps.id"))  # or Admin ID
    changed_at = Column(DateTime, default=datetime.utcnow)

class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(Integer, primary_key=True)
    sender_name = Column(String(100), nullable=False)
    platform = Column(String(50), nullable=False)  # Messenger, Instagram
    lead_id = Column(Integer, ForeignKey('leads.id'))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)