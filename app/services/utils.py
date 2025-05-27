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