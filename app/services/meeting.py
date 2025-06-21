from datetime import datetime
from app.database import db
from app.models.models import Meeting, Notification, SalesRep,ReminderLog
from sqlalchemy.orm import joinedload
from datetime import timedelta
from flask_sqlalchemy import SQLAlchemy
from app.database import db



def check_and_notify_pending_notes():
    try:
        now = datetime.utcnow()
        meetings = db.query(Meeting).options(joinedload(Meeting.lead)).filter(
            Meeting.status == "confirmed",
            Meeting.meeting_time < now,
            Meeting.notes == None
        ).all()

        for meeting in meetings:
            # Check if notification already exists for this meeting
            existing = db.query(Notification).filter_by(
                lead_id=meeting.lead_id,
                sender_name=meeting.lead.name,  # optional, can change to meeting.id
                platform="system",
                is_read=False
            ).first()

            if not existing:
                notif = Notification(
                    sender_name=meeting.lead.name,
                    platform="system",
                    lead_id=meeting.lead_id,
                    is_read=False,
                    created_at=datetime.utcnow()
                )
                db.add(notif)
                print(f"🔔 Notification queued for meeting with {meeting.lead.name}")

        db.commit()
    except Exception as e:
        print("❌ Error in meeting reminder task:", e)
        db.rollback()
    finally:
        db.close()


from datetime import timedelta, timezone
import pytz
from app.services.task import send_whatsapp_reminder

from datetime import datetime, timedelta, timezone
import pytz
from app.services.task import send_whatsapp_reminder

def schedule_pre_meeting_reminders(lead, meeting_time_utc, db):
    # ✅ Safety: ensure meeting_time_utc is naive UTC
    if meeting_time_utc.tzinfo is not None:
        meeting_time_utc = meeting_time_utc.astimezone(timezone.utc).replace(tzinfo=None)

    # Use sales rep timezone for calculating reminders
    rep_tz = pytz.timezone(lead.sales_rep.timezone or "Asia/Karachi")
    local_time = pytz.utc.localize(meeting_time_utc).astimezone(rep_tz)

    print("✅ Meeting scheduled at local:", local_time.strftime("%Y-%m-%d %I:%M %p"))

    local_reminders = [
        local_time - timedelta(minutes=30),
        local_time - timedelta(minutes=5),
    ]

    for local_reminder_time in local_reminders:
        # ✅ Convert back to naive UTC for DB & Celery
        utc_reminder_time = local_reminder_time.astimezone(pytz.utc).replace(tzinfo=None)

        reminder = ReminderLog(
            lead_id=lead.id,
            purpose_id=1,
            scheduled_for=utc_reminder_time,
            status="pending"
        )
        db.add(reminder)
        db.flush()

        utc_reminder_time = local_reminder_time.astimezone(pytz.utc)

        # 2️⃣ Then strip tzinfo before sending to Celery
        eta_naive = utc_reminder_time.replace(tzinfo=None)

        # 3️⃣ Now schedule properly
        send_whatsapp_reminder.apply_async(args=[reminder.id], eta=eta_naive)

    db.commit()