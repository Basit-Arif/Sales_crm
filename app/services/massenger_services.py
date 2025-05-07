# ✅ 2. Function to fetch user's name
import os
import requests
from dotenv import load_dotenv
from datetime import datetime
from app.database import SessionLocal
from app.models.models import LeadMessage
load_dotenv()


def get_user_name(psid: str) -> str | None:
    url = f"https://graph.facebook.com/{psid}"
    params = {
        "fields": "first_name,last_name",
        "access_token": os.getenv("PAGE_ACCESS_TOKEN")
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        first = data.get("first_name")
        last = data.get("last_name")
        return f"{first} {last}"
    else:
        print("❌ Error fetching name:", response.text)
        return None
    


def send_message(psid: str, text: str,lead_id: int,message_type="text"):
    db = SessionLocal()

    # 📝 Step 1: Save the message first with status = 'pending'
    new_message = LeadMessage(
        lead_id=lead_id,
        sender="rep",
        content=text,
        message_type=message_type,
        direction="out",
        status="pending",
        timestamp=datetime.utcnow()
    )
    db.add(new_message)
    db.commit()  # Commit to get the ID

    # 🌐 Step 2: Try sending to Facebook
    url = "https://graph.facebook.com/v17.0/me/messages"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "recipient": {"id": psid},
        "message": {"text": text},
        "messaging_type": "MESSAGE_TAG",
        "tag": "HUMAN_AGENT"
    }
    params = {
        "access_token": os.getenv("PAGE_ACCESS_TOKEN")
    }

    response = requests.post(url, headers=headers, params=params, json=payload)
    print("📤 Message sent:", response.text)
    print("📡 Status Code:", response.status_code)

    try:
        result = response.json()
        if response.status_code == 200 and "message_id" in result:
            new_message.status = "sent"
            new_message.platform_message_id = result["message_id"]
        else:
            new_message.status = "failed"
    except Exception as e:
        print("❌ Error while processing Facebook response:", e)
        new_message.status = "failed"

    db.commit()
    db.close()
    return response
