from datetime import datetime
import pytz

def convert_utc_to_timezone(utc_dt, timezone_str="Asia/Karachi", fmt="%b %d, %Y %I:%M %p", as_string=True):
    """
    Convert a UTC datetime to a specified timezone.
    If as_string=True, return a formatted string; otherwise return a datetime object.
    """
    if not isinstance(utc_dt, datetime):
        return utc_dt  # or raise ValueError("Expected datetime object")

    target_tz = pytz.timezone(timezone_str)

    if utc_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(utc_dt)

    localized = utc_dt.astimezone(target_tz)
    return localized.strftime(fmt) if as_string else localized
from app.models.models import Company
from flask import flash

from sqlalchemy.exc import IntegrityError

def create_company(database, name, messenger_page_id, messenger_access_token):
    if not (name and messenger_page_id and messenger_access_token):
        raise ValueError("❌ Missing required Messenger info.")

    existing = database.query(Company).filter(
        (Company.name == name) |
        (Company.messenger_page_id == messenger_page_id)
    ).first()

    if existing:
        raise ValueError("❌ Company with this name or Messenger Page ID already exists.")

    try:
        company = Company(
            name=name,
            messenger_page_id=messenger_page_id,
            messenger_access_token=messenger_access_token
        )
        database.add(company)
        database.commit()
        return company
    except IntegrityError:
        database.rollback()
        raise ValueError("❌ Database rejected duplicate Messenger Page ID.")