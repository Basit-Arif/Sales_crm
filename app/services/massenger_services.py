# ✅ 2. Function to fetch user's name
import os
import requests
from dotenv import load_dotenv
from datetime import datetime
from app.models import db,local_now
from app.models.models import LeadMessage
from flask import current_app
from app import socketio

load_dotenv()


def get_user_name(psid: str, access_token: str) -> str | None:
    url = f"https://graph.facebook.com/{psid}"
    params = {
        "fields": "first_name,last_name",
        "access_token": access_token
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        return f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
    else:
        print("❌ Error fetching Messenger name:", response.text)
        return None
    

def get_instagram_username(access_token):
    # Step 1: Get list of pages
    pages_url = f"https://graph.facebook.com/v19.0/me/accounts?access_token={access_token}"
    pages_response = requests.get(pages_url)
    pages_data = pages_response.json()

    for page in pages_data.get('data', []):
        page_id = page['id']
        # Step 2: Get Instagram Business Account ID
        ig_account_url = f"https://graph.facebook.com/v19.0/{page_id}?fields=instagram_business_account&access_token={access_token}"
        ig_account_response = requests.get(ig_account_url)
        ig_account_data = ig_account_response.json()

        ig_business_account = ig_account_data.get('instagram_business_account')
        if ig_business_account:
            ig_user_id = ig_business_account['id']
            # Step 3: Get Instagram Username
            ig_user_url = f"https://graph.facebook.com/v19.0/{ig_user_id}?fields=username&access_token={access_token}"
            ig_user_response = requests.get(ig_user_url)
            ig_user_data = ig_user_response.json()
            return ig_user_data.get('username')
    return None
    
def get_lead_name(psid: str, platform: str, access_token: str) -> str | None:
    if platform == "messenger":
        return get_user_name(psid, access_token)
    elif platform == "instagram":
        return get_instagram_username(access_token)
    else:
        print("❌ Unknown platform for lead name fetch.")
        return None


# def send_message(psid: str, text: str, lead_id: int, access_token: str, message_type="text", platform="messenger"):
#     # Step 1: Save message with pending status
#     new_message = LeadMessage(
#         lead_id=lead_id,
#         sender="rep",
#         content=text,
#         message_type=message_type,
#         direction="out",
#         status="pending",
#         timestamp=local_now()
#     )
#     db.session.add(new_message)
#     db.session.commit()

#     # Step 2: Prepare request
#     headers = {"Content-Type": "application/json"}
#     params = {"access_token": access_token}

#     if platform == "messenger":
#         url = "https://graph.facebook.com/v17.0/me/messages"

#         if message_type == "image":
#             payload = {
#                 "recipient": {"id": psid},
#                 "message": {
#                     "attachment": {
#                         "type": "image",
#                         "payload": {
#                             "url": text,  # Here, text holds the image URL
#                             "is_reusable": True
#                         }
#                     }
#                 },
#                 "messaging_type": "MESSAGE_TAG",
#                 "tag": "HUMAN_AGENT"
#             }
#         else:
#             payload = {
#                 "recipient": {"id": psid},
#                 "message": {"text": text},
#                 "messaging_type": "MESSAGE_TAG",
#                 "tag": "HUMAN_AGENT"
#             }

#     elif platform == "instagram":
#         url = "https://graph.facebook.com/v17.0/me/messages"

#         if message_type == "image":
#             payload = {
#                 "recipient": {"id": psid},
#                 "message": {
#                     "attachment": {
#                         "type": "image",
#                         "payload": {
#                             "url": text
#                         }
#                     }
#                 },
#                 "messaging_type": "RESPONSE"
#             }
#         else:
#             payload = {
#                 "recipient": {"id": psid},
#                 "message": {"text": text},
#                 "messaging_type": "RESPONSE"
#             }

#     else:
#         print("❌ Unknown platform")
#         new_message.status = "failed"
#         db.session.commit()
#         return None

#     # Step 3: Send request
#     response = requests.post(url, headers=headers, params=params, json=payload)
#     print("📤 Message response:", response.text)

#     try:
#         result = response.json()
#         if response.status_code == 200 and "message_id" in result:
#             new_message.status = "sent"
#             new_message.platform_message_id = result["message_id"]
#         else:
#             new_message.status = "failed"
#     except Exception as e:
#         print("❌ JSON decode error:", e)
#         new_message.status = "failed"

#     db.session.commit()
#     db.session.remove()
#     return response


from app.models import db
from app.models.models import LeadMessage
 # your local_now function

def create_pending_message(psid, text, lead_id, message_type, platform):
    message = LeadMessage(
        lead_id=lead_id,
        sender="rep",
        content=text,
        message_type=message_type,
        direction="out",
        status="pending",
        timestamp=local_now()
    )
    db.session.add(message)
    db.session.flush()   # ✅ Assigns ID without full commit
    db.session.commit()  # ✅ Ensures message is saved before async
    return message.id


from time import sleep

def get_message_with_retry(message_id, retries=5, delay=1):
    sleep(0.5)  # 🔍 Small delay before first fetch
    for attempt in range(retries):
        message = db.session.query(LeadMessage).filter_by(id=message_id).first()
        if message:
            return message
        print(f"⏳ Retry {attempt+1}/{retries}: Message {message_id} not found")
        sleep(delay)
    return None



def send_message(message_id, psid, text, access_token, message_type="text", platform="messenger"):
    session = db.session
    message = get_message_with_retry(message_id)
    if not message:
        print("❌ Message not found")
        return None

    # ✅ Add this block
    if message.message_type in ["image", "file"]:
        message.content = text

    headers = {"Content-Type": "application/json"}
    params = {"access_token": access_token} 
    url = "https://graph.facebook.com/v17.0/me/messages"

    if platform == "messenger":
        payload = {
            "recipient": {"id": psid},
            "message": {"text": text} if message_type == "text" else {
                "attachment": {
                    "type": "image",
                    "payload": {"url": text, "is_reusable": True}
                }
            },
            "messaging_type": "MESSAGE_TAG",
            "tag": "HUMAN_AGENT"
        }
    elif platform == "instagram":
        payload = {
            "recipient": {"id": psid},
            "message": {"text": text} if message_type == "text" else {
                "attachment": {
                    "type": "image",
                    "payload": {"url": text}
                }
            },
            "messaging_type": "RESPONSE"
        }
    else:
        message.status = "failed"
        session.commit()
        return None

    try:
        response = requests.post(url, headers=headers, params=params, json=payload)
        result = response.json()

        if response.status_code == 200 and "message_id" in result:
            message.status = "sent"
            message.platform_message_id = result["message_id"]
        else:
            message.status = "failed"
    except Exception as e:
        print("❌ Send error:", e)
        message.status = "failed"

    message.timestamp = datetime.utcnow()
    session.commit()

    socketio.emit(
        "message_status_update",
        {
            "lead_id": message.lead_id,
            "message_id": message.id,
            "status": message.status
        },
        room=f"lead_{message.lead_id}"
    )

    return response