import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ACCESS_TOKEN = os.getenv("Whatsapp_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")


def send_lead_template(rep_phone: str, rep_name: str, lead_name: str):
    """
    Send a WhatsApp template message to the assigned sales rep with lead details.
    """
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": rep_phone.lstrip('+'),  # Format to E.164 (e.g., 923001234567)
        "type": "template",
        "template": {
            "name": "lead_",  # TODO: Replace with your actual template name
            "language": {
                "code": "en"
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": rep_name},
                        {"type": "text", "text": lead_name}
                    ]
                }
            ]
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    print("\ud83d\udce4 WhatsApp sent:", response.status_code)
    print(response.text)

    return response.status_code, response.json()
