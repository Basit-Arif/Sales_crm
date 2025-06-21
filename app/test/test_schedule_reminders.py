import pytest
from datetime import datetime, timedelta, timezone
import pytz

from app.models.models import SalesRep, Lead, ReminderLog,Company,User,ReminderPurpose
from app.services.meeting import schedule_pre_meeting_reminders

@pytest.fixture
def sample_db(db_session):
    """ Prepopulate dummy company, user, sales rep & lead """
    """ Prepopulate company, user, sales rep, reminder purpose & lead """
    company = Company(id=1, name="Test Company", messenger_page_id="245737865859808", messenger_access_token="EAAaxj3IRPs4BOZB4ZBu5bWdqh6qi4LHXZAqDzdCjLiZBGhizFU45GiA5Sm4lufMryldYAhzMcDoXoGJ5k79OXyK37HZAFHUYdgGrcdk6awxaGBHoD6XeLRwBpl1pDem72ihYc0fYYWwJijGtwGlcLpuQXvQ61PWRIpcKBxgsrAjOiUVLZBn84ZAbMm6AyZAR4yph1XZBs7xirmOpD3uz5")
    user = User(id=1, username="testuser", password="hashed", is_admin=False)
    
    db_session.add(company)
    db_session.add(user)
    db_session.flush()

    sales_rep = SalesRep(
        id=1,
        name="Basit",
        company_id=company.id,
        user_id=user.id,
        timezone="Asia/Karachi",
        phone_number="03242586315"
    )
    db_session.add(sales_rep)

    # 🔧 Insert Reminder Purpose
    reminder_purpose = ReminderPurpose(id=1, name="Meeting")
    db_session.add(reminder_purpose)

    lead = Lead(
        id=1,
        name="Ms John",
        sales_rep_id=1,
        sales_rep=sales_rep
    )
    db_session.add(lead)

    db_session.commit()

    return db_session, lead

def test_schedule_reminders(sample_db):
    db_session, lead = sample_db

    # Meeting time 2 hours from now
    meeting_time_utc = datetime.now(timezone.utc) + timedelta(hours=2)

    # Execute reminder scheduler
    schedule_pre_meeting_reminders(lead, meeting_time_utc, db_session)

    # Verify reminders are inserted
    reminders = db_session.query(ReminderLog).filter_by(lead_id=lead.id).all()
    assert len(reminders) == 2, "Should create 2 reminders (30min and 5min)"

    for reminder in reminders:
        scheduled_for = reminder.scheduled_for.replace(tzinfo=timezone.utc)
        delta_minutes = round((meeting_time_utc - scheduled_for).total_seconds() / 60)
        assert delta_minutes in [30, 5], f"Reminder time offset incorrect: {delta_minutes}"

    print("✅ Reminder scheduling test passed.")