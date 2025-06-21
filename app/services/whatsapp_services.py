import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()



def send_lead_template(rep_phone: str, rep_name: str, lead_name: str, lead_phone: str, lead_status: str, assigned_date: str):
    """
    Send a WhatsApp template message to the assigned sales rep with lead details.
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()
    ACCESS_TOKEN = os.getenv("Whatsapp_ACCESS_TOKEN")
    PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": rep_phone.lstrip('+'),
        "type": "template",
        "template": {
            "name": "lead_details",  # Replace with your actual template name
            "language": {
                "code": "en"
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": rep_name},
                        {"type": "text", "text": lead_name},
                        {"type": "text", "text": lead_phone},
                        {"type": "text", "text": lead_status},
                        {"type": "text", "text": assigned_date}
                    ]
                }
            ]
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    return response.json()



def send_meeting_reminder_function(rep_phone, rep_name, lead_name, time_str, timezone_str, minutes_left):
    print("In send_meeting_reminder_function")
    import os
    import requests
    from dotenv import load_dotenv
    load_dotenv()

    ACCESS_TOKEN = os.getenv("Whatsapp_ACCESS_TOKEN")
    PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

    if not PHONE_NUMBER_ID:
        print("❌ PHONE_NUMBER_ID is missing or not loaded from .env")

    if not ACCESS_TOKEN:
        print("❌ ACCESS_TOKEN is missing or not loaded from .env")

    if rep_phone.startswith("03"):
        rep_phone = "92" + rep_phone[1:]

    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": rep_phone,
        "type": "template",
        "template": {
            "name": "meeting_reminder",
            "language": {"code": "en"},
            "components": [
                {"type": "body", "parameters": [
                    {"type": "text", "text": rep_name},
                    {"type": "text", "text": lead_name},
                    {"type": "text", "text": time_str},
                    {"type": "text", "text": timezone_str},
                    {"type": "text", "text": str(minutes_left)}
                ]}
            ]
        }
    }

    try:
        print("📤 Sending request to WhatsApp API...")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # This will raise HTTPError if not 2xx
        print("✅ WhatsApp API Response:", response.json())
        return response.json()

    except requests.exceptions.RequestException as e:
        print("❌ Exception occurred while sending WhatsApp message:", str(e))
        return {"error": str(e)}