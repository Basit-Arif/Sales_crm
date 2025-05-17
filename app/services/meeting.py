from datetime import datetime
from app.database import SessionLocal
from app.models.models import Meeting, Notification, SalesRep
from sqlalchemy.orm import joinedload


def check_and_notify_pending_notes():
    db = SessionLocal()
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