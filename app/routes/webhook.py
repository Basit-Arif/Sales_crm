from flask import Flask,Blueprint,render_template,url_for,redirect,jsonify,request,flash,session
from app.models.models import Lead,SalesRep,Company,LeadMessage, Notification
import os
from app.services.massenger_services import get_user_name
from app.services.lead_distribution_logic import get_next_sales_rep
from dotenv import load_dotenv
from app.database import SessionLocal
from datetime import datetime
from app import socketio
from app.services.task import detect_meeting_intent_task,detect_meeting_intent

# Load environment variables
load_dotenv()
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")


webhook_bp = Blueprint("webhook", __name__, url_prefix="/webhook")


@webhook_bp.route("/massenger", methods=["GET"])
@webhook_bp.route("massenger", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook Verified")
        return challenge, 200
    return "Forbidden", 403


@webhook_bp.route("massenger", methods=["POST"])
@webhook_bp.route("/massenger", methods=["POST"])
def handle_webhook():
    print("🚀 Webhook hit!")
    body = request.get_json()
    print("📩 Webhook payload received:", body)

    if not body:
        return jsonify({"error": "Empty or invalid payload"}), 400

    platform = body.get("object")  # 'page' for Messenger, 'instagram' for IG

    for entry in body.get("entry", []):
        page_id = entry.get("id")

        if platform in ["page", "instagram"]:
            for event in entry.get("messaging", []):
                
                
                # 🚫 Ignore system events
                if "delivery" in event:
                    for mid in event["delivery"].get("mids", []):
                        db = SessionLocal()
                        msg = db.query(LeadMessage).filter_by(platform_message_id=mid).first()
                        if msg:
                            msg.status = "delivered"
                            db.commit()
                            socketio.emit("message_status_update", {
                                "message_id": msg.id,
                                "status": "delivered"
                            })
                        db.close()
                    continue

                # 🔁 Handle read receipts
                if "read" in event:
                    sender_id = event["sender"]["id"]
                    db = SessionLocal()
                    lead = db.query(Lead).filter_by(external_user_id=sender_id).first()
                    if lead:
                        messages = db.query(LeadMessage).filter_by(lead_id=lead.id, sender="rep", status="delivered").all()
                        for msg in messages:
                            msg.status = "read"
                            msg.read_at = datetime.utcnow()
                        db.commit()
                    db.close()
                    continue

                # 🎯 Only process if there is actual message content
                message = event.get("message", {})

                # Detect and extract the message type
                content = None
                message_type = None

                if "text" in message:
                    content = message["text"]
                    message_type = "text"

                elif "attachments" in message:
                    attachment = message["attachments"][0]
                    attachment_type = attachment.get("type")
                    
                    if attachment_type == "image":
                        content = attachment["payload"]["url"]
                        message_type = "image"
                    elif attachment_type == "file":
                        content = attachment["payload"]["url"]
                        message_type = "file"
                    else:
                        print(f"❌ Unsupported attachment type '{attachment_type}'. Skipping.")
                        continue

                if not content or not message_type:
                    print("❌ No valid content found in message. Skipping.")
                    continue

                # 🎯 Pass it for further processing
                if platform == "page":
                    handle_messenger_event(event, page_id, lead_platform="messenger", content=content, message_type=message_type)
                elif platform == "instagram":
                    handle_instagram_event(event, page_id, lead_platform="instagram", content=content, message_type=message_type)

    return jsonify({"status": "received"}), 200

    

def handle_messenger_event(event, page_id, lead_platform, content, message_type):
    print(f"📥 Incoming message type: {message_type}")
    sender_id = event["sender"]["id"]
    # print(f"📩 Messenger: {session["sales_rep_id"]}")

    user_name = get_user_name(sender_id)
    if not user_name:
        return

    try:
        db = SessionLocal()
        lead = db.query(Lead).filter_by(external_user_id=sender_id).first()

        if not lead:
            # Assign rep if lead doesn't exist
            assigned_rep = get_next_sales_rep(db)
            lead = Lead(
                external_user_id=sender_id,
                platform=lead_platform,
                name=user_name,
                message=content,  # Save first message content
                sales_rep_id=assigned_rep.id,
                ad_repr="Messenger",
                assigned_at=datetime.utcnow(),
                last_active_at=datetime.utcnow(),
                status="active"
            )
            db.add(lead)
            db.commit()
            print("🆕 New lead created.")

        else:
            lead.last_active_at = datetime.utcnow()
            db.commit()

        # Save message
        new_message = LeadMessage(
            lead_id=lead.id,
            sender="user",
            content=content,
            message_type=message_type,
            direction="in",
            status="received",
        )
        db.add(new_message)
        db.commit()
        detect_meeting_intent.delay(lead.id, content)

        room = f"user_{lead.sales_rep.user_id}" 
        print(f"this is {room}")
        # Emit to socket for real-time update
        socketio.emit("new_message", {
            "lead_id": str(lead.id),
            "sender": "user",
            "content": content,
            "sender_name": lead.name,
            "message_type": message_type,
            "timestamp": datetime.utcnow().strftime("%d %b %Y, %I:%M %p")
        }, to=room)


        # Save notification
        notification = Notification(
            sender_name=lead.name,
            platform=lead.platform,
            lead_id=lead.id
        )
        db.add(notification)
        db.commit()


        # Unread count emit
        unread_messages = db.query(LeadMessage).filter_by(
            lead_id=lead.id,
            sender="user",
            is_read=False
        ).all()

        socketio.emit("unread_update", {
            "lead_id": str(lead.id),
            "unread_count": len(unread_messages)
        }, to=room)

    except Exception as e:
        print("❌ Error handling Messenger event:", str(e))
        db.rollback()
    finally:
        db.close()

    # db.session.commit()
    # send_message(sender_id, f"Hi {user_name}, thanks for messaging us!")


def handle_instagram_event(value, page_id):
    # sender_id = value.get("sender", {}).get("id")
    # message_text = value.get("message", {}).get("text", "")

    # print(f"📸 Instagram: {sender_id} said: {message_text}")

    # user_name = get_user_name(sender_id)
    # if not user_name:
    #     return

    # lead = db.session.query(Lead).filter_by(psid=sender_id).first()
    # if lead:
    #     lead.last_active_at = datetime.utcnow()
    #     print("🔁 Instagram lead already exists")
    # else:
    #     assigned_rep = get_next_sales_rep(db.session)
    #     lead = Lead(
    #         psid=sender_id,
    #         name=user_name,
    #         message=message_text,
    #         sales_rep_id=assigned_rep.id,
    #         ad_repr="Instagram",
    #         assigned_at=datetime.utcnow(),
    #         last_active_at=datetime.utcnow(),
    #         status="active"
    #     )
    #     db.session.add(lead)
    #     send_lead_template(assigned_rep.phone_number, assigned_rep.name, user_name)
    #     print(f"✅ New Instagram lead assigned to {assigned_rep.name}")

    # db.session.commit()
    # send_message(sender_id, f"Hi {user_name}, thanks for messaging us!")
    print(f"✅ New instagram lead ")
    pass
