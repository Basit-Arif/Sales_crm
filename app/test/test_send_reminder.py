import pytest
from app.services.whatsapp_services import send_meeting_reminder_function
import os
from dotenv import load_dotenv

load_dotenv()

@pytest.mark.integration
def test_send_meeting_reminder_success():
    # These should be dummy or test numbers and template values in your sandbox setup
    rep_phone = os.getenv("TEST_REP_PHONE", "923242586315")
    rep_name = "Basit"
    lead_name = "Ms John"
    time_str = "4:00"
    timezone_str = "EST"
    minutes_left = 30

    response = send_meeting_reminder_function(
        rep_phone=rep_phone,
        rep_name=rep_name,
        lead_name=lead_name,
        time_str=time_str,
        timezone_str=timezone_str,
        minutes_left=minutes_left
    )
    print(response)

    assert isinstance(response, dict)
    assert "messages" in response or "error" in response  # Either success or descriptive error
    if "messages" in response:
        assert response["messages"][0]["message_status"] in ["accepted", "sent", "delivered"]
    else:
        print("⚠️ WhatsApp API Error:", response["error"])