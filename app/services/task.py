# meeting_pipeline.py

# from app.celery_worker import celery
from app.celery_app import celery
from app.extension import db
from app.models.models import Lead, LeadMessage, Meeting,LeadComment
from sqlalchemy import func
from datetime import datetime,timedelta
import requests
import pytz
from dateutil import parser 
from collections import defaultdict
import re
from app.services.whatsapp_services import send_meeting_reminder_function


# replace with your actual Flask app engine




# from app.services.task import celery



# -----------------------------
# Celery Setup
# -----------------------------
# celery = celery('tasks', broker='redis://localhost:6379/0')


# -----------------------------
# Stage 1: Regex-based Meeting Intent Detector
# -----------------------------
def is_meeting_related(message: str) -> bool:
    msg = message.lower()
    return bool(re.search(
        r"\b(meet|meeting|schedule|call|zoom|google meet|teams|fix.*time|set.*time|book.*call|talk.*at|reschedule|cancel)\b",
        msg
    ))

# -----------------------------
# Stage 2: LLM-like Placeholder Extractor (Simulated)
# -----------------------------
def extract_meeting_time_llm(message: str) -> dict:
    time_match = re.search(r"\b(?:at\s*)?(\d{1,2}[:.]\d{2}\s*[ap]m|\d{1,2}\s*[ap]m)\b", message, re.I)
    time_string = time_match.group(1) if time_match else None

    date_match = re.search(r"\b(tomorrow|today|day after tomorrow|\d{1,2}(st|nd|rd|th)?\s+\w+|\w+\s+\d{1,2}(st|nd|rd|th)?)\b", message, re.I)
    date_str = date_match.group(1) if date_match else None

    date = None
    try:
        if date_str:
            if "tomorrow" in date_str:
                date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            elif "day after tomorrow" in date_str:
                date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
            elif "today" in date_str:
                date = datetime.now().strftime('%Y-%m-%d')
            else:
                date = parser.parse(date_str, fuzzy=True, dayfirst=True).strftime('%Y-%m-%d')
    except Exception:
        date = datetime.now().strftime('%Y-%m-%d')

    return {
        "time_string": time_string,
        "date": date,
        "timezone": "Asia/Karachi",
        "intent": "schedule_meeting",
        "confidence": 0.95 if time_string or date_str else 0.5
    }

# -----------------------------
# Message Buffer to Track Last Few Messages per User
# -----------------------------
class MessageBuffer:
    def __init__(self, window_size=3):
        self.buffer = defaultdict(list)
        self.window_size = window_size

    def add_message(self, user_id: str, message: str):
        self.buffer[user_id].append(message)
        if len(self.buffer[user_id]) > self.window_size:
            self.buffer[user_id].pop(0)

    def get_combined_message(self, user_id: str) -> str:
        return " ".join(self.buffer[user_id])

    def clear(self, user_id: str):
        self.buffer[user_id] = []

# -----------------------------
# Main Detector with Background Task
# -----------------------------
buffer = MessageBuffer()

def detect_meeting_intent_local(lead_id: int, message_content: str):
    print("in detect")
    session = db.session
    try:
        messages = (
            session.query(LeadMessage)
            .filter_by(lead_id=lead_id)
            .order_by(LeadMessage.timestamp.desc())
            .limit(3)
            .all()
        )
        recent_texts = [m.content for m in reversed(messages) if m.message_type == "text"]
        combined = " ".join(recent_texts)

        buffer.add_message(str(lead_id), message_content)
        combined_message = buffer.get_combined_message(str(lead_id))

        if is_meeting_related(combined_message):
            result = extract_meeting_time_llm(combined_message)
            print("Regex Result:", result)

            try:
                response = requests.post("http://localhost:8000/process", json={
                    "lead_message": combined_message,
                    "lead_id": lead_id
                })

                print("Status Code:", response.status_code)
                print("Raw Response:", response.text)

                if response.ok:
                    data = response.json()
                    print("LLM Result:", data)
                else:
                    print("❌ API returned error")

            except Exception as e:
                print("❌ Request failed:", e)
               
            if result['confidence'] >= 0.8:
                lead = session.query(Lead).get(lead_id)
                meeting_time = parser.parse(f"{result['date']} {result['time_string']}")

                new_meeting = Meeting(
                    sales_rep_id=lead.sales_rep_id,
                    lead_id=lead_id,
                    meeting_time=meeting_time,
                    original_message=message_content,
                    detected_time_string=result['time_string'],
                    status="pending"
                )
                session.add(new_meeting)
                session.commit()
                buffer.clear(str(lead_id))
                print("Meeting created:", new_meeting.id)
    except Exception as e:
        print("❌ Error:", e)
    finally:
        session.close()


@celery.task
def detect_meeting_intent_task(lead_id, message_content):
    detect_meeting_intent_local(lead_id, message_content)

@celery.task(name="detect_meeting_intent")
def detect_meeting_intent(lead_id: int, message_content: str):
    from app import create_app
    app = create_app()
    session = db.session
    with app.app_context():
        try:
            print(f"🎯 Task started for lead: {lead_id}")
            print(f"session id: {session}")
            messages = (
                session.query(LeadMessage)
                .filter_by(lead_id=lead_id)
                .order_by(LeadMessage.timestamp.desc())
                .limit(3)
                .all()
            )
            text_msgs = [m.content for m in reversed(messages) if m.message_type == "text"]
            combined = " ".join(text_msgs)

            print("Combined text:", combined)

            # Fake detection
            response = requests.post("http://localhost:8000/process", json={
                "lead_message": combined,
                "lead_id": lead_id
            }, timeout=10)

            result = response.json().get("response", {})

            if not result.get("meeting_intent"):
                return

            local_naive = parser.parse(f"{result['meeting_date']} {result['meeting_time']}")
            client_tz = pytz.timezone(result.get("timezone", "Asia/Karachi"))
            localized = client_tz.localize(local_naive)
            meeting_time_utc = localized.astimezone(pytz.utc)

            lead = session.query(Lead).get(lead_id)
            if not lead:
                print("Lead not found")
                return

            meeting = Meeting(
                sales_rep_id=lead.sales_rep_id,
                lead_id=lead.id,
                meeting_time_utc=meeting_time_utc,
                client_timezone=result["timezone"],
                rep_timezone="Asia/Karachi",
                original_message=message_content,
                detected_date_string=result["meeting_date"],
                detected_time_string=result["meeting_time"],
                status="pending"
            )
            session.add(meeting)
            session.commit()

            print("✅ Meeting saved")
        except Exception as e:
            print("❌ Internal error:", e)
            session.rollback()
        finally:
            session.close()
# @celery.task(name="detect_meeting_intent")
# def detect_meeting_intent(lead_id: int, message_content: str):
#     from app import create_app
#     app = create_app()
#     session = db.session
#     with app.app_context():
#         try:
#             session = db.session
#             print(f"🎯 Task started for lead: {lead_id}")
#             lead = session.query(Lead).get(lead_id)
#             print("Lead:", lead.name if lead else "Not found")
#         except Exception as e:
#             print("❌ Task error:", e)
#             session.rollback()
#         finally:
#             session.close()
    
from pytz import timezone

@celery.task(name="summarize_leads_for_date")
def summarize_leads_for_date(lead_id: int, summary_date: str):
    print('hello')
    from app import create_app
        
    from pytz import timezone
    print("hello")
    app = create_app()
    session = db.session
    with app.app_context():
        try:
            date_obj = datetime.strptime(summary_date, "%Y-%m-%d").date()
            tz = timezone("Asia/Karachi")
            start_of_day = tz.localize(datetime.combine(date_obj, datetime.min.time())).astimezone(pytz.utc)
            end_of_day = tz.localize(datetime.combine(date_obj, datetime.max.time())).astimezone(pytz.utc)

            # Check the latest message timestamp
            latest_msg = session.query(LeadMessage).filter_by(lead_id=lead_id).order_by(LeadMessage.timestamp.desc()).first()
            if latest_msg and latest_msg.timestamp.astimezone(pytz.utc) > end_of_day:
                print("⏩ Skipping summary: newer message exists after target summary date.")
                return

            messages = session.query(LeadMessage).filter(
                LeadMessage.lead_id == lead_id,
                LeadMessage.timestamp >= start_of_day,
                LeadMessage.timestamp <= end_of_day
            ).order_by(LeadMessage.timestamp.asc()).all()

            if not messages:
                print("⚠️ No messages found for this date. Skipping summarization.")
                return
            print(f"📅 Summarizing messages for lead {lead_id} on {summary_date}")

            try:
                formatted_text = "\n".join(
                f"{msg.timestamp.strftime('%H:%M')} ({msg.sender}): {msg.content}"
                for msg in messages
                )
                print("in this")              
                response = requests.post("http://localhost:8000/summarize", json={
                    "lead_id": lead_id,
                    "summary_date": summary_date,
                    "formatted_text": formatted_text
                })

                if response.status_code == 200:
                    summary_output = response.json().get("summary")
                    session.merge(LeadComment(
                        lead_id=lead_id,
                        summary_date=date_obj,
                        content=summary_output,
                        generated_by="gpt",
                        created_at=datetime.now()
                    ))
                else:
                    print(f"❌ Failed for lead {lead_id}: Status {response.status_code}")
            except Exception as e:
                print(f"❌ Request error for lead {lead_id}: {e}")

            session.commit()
            print(f"✅ Summarized lead {lead_id} for {summary_date}")
        except Exception as e:
            print("❌ Summarization batch failed:", e)
            session.rollback()
        finally:
            session.close()
# -----------------------------
# Example
# -----------------------------
# if __name__ == "__main__":
#     # detect_meeting_intent_local(3, "hey how are you")
#     detect_meeting_intent(3, "hey how are you")





# app/services/task.py



from datetime import datetime, timezone
import pytz
from app.models import db
from app.models.models import ReminderLog, Lead, Meeting
from app.services.whatsapp_services import send_meeting_reminder_function

@celery.task(name="send_whatsapp_reminder")
def send_whatsapp_reminder(reminder_id):
    import logging
    logger = logging.getLogger(__name__)

    try:
        reminder = db.session.get(ReminderLog, reminder_id)
        if not reminder:
            logger.warning(f"⚠️ Reminder {reminder_id} not found.")
            return

        lead = db.session.get(Lead, reminder.lead_id)
        if not lead or not lead.sales_rep or not lead.sales_rep.phone_number:
            reminder.status = "failed"
            db.session.commit()
            return

        meeting = db.session.query(Meeting).filter_by(lead_id=lead.id).order_by(Meeting.meeting_time_utc.desc()).first()
        if not meeting:
            reminder.status = "failed"
            db.session.commit()
            return

        # ✅ helper to ensure meeting_time is aware
        def make_aware(dt):
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        meeting_time = make_aware(meeting.meeting_time_utc)
        now_utc = datetime.now(timezone.utc)

        minutes_left = int((meeting_time - now_utc).total_seconds() // 60)
        rep_tz = pytz.timezone(lead.sales_rep.timezone or "Asia/Karachi")

        # ✅ SAFE conversion - no localize anymore
        local_meeting_time = meeting_time.astimezone(rep_tz)
        time_str = local_meeting_time.strftime("%I:%M %p")
        timezone_str = rep_tz.zone

        response_json = send_meeting_reminder_function(
            rep_phone=lead.sales_rep.phone_number,
            rep_name=lead.sales_rep.name,
            lead_name=lead.name,
            time_str=time_str,
            timezone_str=timezone_str,
            minutes_left=minutes_left
        )

        if 'error' not in response_json:
            reminder.status = "sent"
        else:
            reminder.status = "failed"
            reminder.retry_count += 1

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        logger.error(f"🔥 CRITICAL ERROR during reminder {reminder_id}: {str(e)}", exc_info=True)