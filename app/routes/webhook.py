from flask import Flask,Blueprint,render_template,url_for,redirect,jsonify,request,flash,session,current_app
from app.models.models import Lead,SalesRep,Company,LeadMessage, Notification
import os
from app.services.massenger_services import get_user_name,get_lead_name
from app.services.lead_distribution_logic import get_next_sales_rep
from dotenv import load_dotenv
from datetime import datetime
from app import socketio
from app.celery_app import celery
from app.services.task import detect_meeting_intent
from app.log_config import log_action
# 




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
        log_action("Webhook verified successfully", actor_type="system", action_type="webhook-verify")
        return challenge, 200
    log_action("Webhook verification failed", actor_type="system", action_type="webhook-verify", level="warning")
    return "Forbidden", 403


@webhook_bp.route("massenger", methods=["POST"])
@webhook_bp.route("/massenger", methods=["POST"])
def handle_webhook():
    body = request.get_json()
    print(body)
    log_action("Webhook payload received", actor_type="system", action_type="webhook-payload")

    if not body:
        log_action("Empty or invalid webhook payload", actor_type="system", action_type="webhook-error", level="error")
        return jsonify({"error": "Empty or invalid payload"}), 400

    platform = body.get("object")

    for entry in body.get("entry", []):
        page_id = entry.get("id")

        if platform in ["page", "instagram"]:
            for event in entry.get("messaging", []):
                try:
                    # Echo handling
                    if "message" in event and event["message"].get("is_echo"):
                        platform_mid = event["message"]["mid"]
                        db = current_app.extensions['sqlalchemy'].session
                        msg = db.query(LeadMessage).filter_by(platform_message_id=platform_mid).first()
                        if msg:
                            msg.status = "sent"
                            db.commit()
                            socketio.emit("message_status_update", {
                                "message_id": msg.id,
                                "status": "sent"
                            }, to=f"user_{msg.lead.sales_rep.user_id}")
                            log_action(f"Echo message marked as sent: {platform_mid}", actor_type="system", action_type="echo")
                        db.close()
                        continue

                    # Delivery receipts
                    if "delivery" in event:
                        for mid in event["delivery"].get("mids", []):
                            db = current_app.extensions['sqlalchemy'].session
                            msg = db.query(LeadMessage).filter_by(platform_message_id=mid).first()
                            if msg:
                                msg.status = "delivered"
                                db.commit()
                                socketio.emit("message_status_update", {
                                    "message_id": msg.id,
                                    "status": "delivered"
                                }, to=f"user_{msg.lead.sales_rep.user_id}")
                                log_action(f"Message marked as delivered: {mid}", actor_type="system", action_type="delivery")
                            db.close()
                        continue

                    # Read receipts
                    if "read" in event:
                        sender_id = event["sender"]["id"]
                        db = current_app.extensions['sqlalchemy'].session
                        lead = db.query(Lead).filter_by(external_user_id=sender_id).first()
                        if lead:
                            messages = db.query(LeadMessage).filter_by(lead_id=lead.id, sender="rep", status="delivered").all()
                            for msg in messages:
                                msg.status = "read"
                                msg.read_at = datetime.now()
                            db.commit()
                            log_action(f"Messages marked as read for lead {lead.id}", actor_type="system", action_type="read")
                        db.close()
                        continue

                    # Get message content
                    message = event.get("message", {})
                    content = None
                    message_type = None

                    if "text" in message:
                        content = message["text"]
                        message_type = "text"
                    elif "attachments" in message:
                        attachment = message["attachments"][0]
                        if attachment.get("type") in ["image", "file"]:
                            content = attachment["payload"]["url"]
                            message_type = attachment["type"]
                        else:
                            log_action(f"Unsupported attachment type: {attachment.get('type')}", level="warning", actor_type="system")
                            continue

                    if not content or not message_type:
                        log_action("No valid content in message", actor_type="system", level="warning")
                        continue

                    # Process message
                    db = current_app.extensions['sqlalchemy'].session
                    if platform == "page":
                        company = db.query(Company).filter(Company.messenger_page_id == page_id.strip()).first()
                    elif platform == "instagram":
                        company = db.query(Company).filter(Company.instagram_page_id == page_id.strip()).first()
                        instagram_id = company.instagram_page_id
                    else:
                        company = None
                    if not company:
                        log_action(f"No company found for page_id: {page_id}", level="error", actor_type="system")
                        return jsonify({"error": "Company not found"}), 400

                    access_token = company.messenger_access_token if platform == "page" else company.instagram_access_token
                    print("this is access token")
                    print(access_token)

                    if platform == "page":
                        handle_messenger_event(event, page_id, "messenger", content, message_type, access_token)
                    elif platform == "instagram":
                        handle_instagram_event(event, page_id, "instagram", content, message_type, access_token,instagram_id)

                except Exception as e:
                    log_action("Unhandled exception in webhook event loop", level="error", actor_type="system", exc_info=True)

    return jsonify({"status": "received"}), 200

    



def handle_messenger_event(event, page_id, lead_platform, content, message_type, access_token):
    sender_id = event["sender"]["id"]
    log_action(f"📥 Incoming message [{message_type}] from {sender_id}", actor_type="system", action_type="message-received")

    user_name = get_lead_name(sender_id, platform="messenger", access_token=access_token)
    if not user_name:
        log_action(f"❌ Could not fetch name for sender {sender_id}", level="warning", actor_type="system")
        return

    try:
        db_instance = current_app.extensions['sqlalchemy']
        db = db_instance.session

        lead = db.query(Lead).filter_by(external_user_id=sender_id).first()

        if not lead:
            # 🔍 Identify company
            company_filter = {
                "messenger": Company.messenger_page_id == page_id,
                "instagram": Company.instagram_page_id == page_id
            }

            company = db.query(Company).filter(company_filter.get(lead_platform)).first()

            if not company:
                log_action(f"❌ No company found for {lead_platform} page_id: {page_id}", level="error", actor_type="system")
                return

            assigned_rep = get_next_sales_rep(db, company.id)
            if not assigned_rep:
                log_action(f"⚠️ No sales reps available for company {company.name}", level="warning", actor_type="system")
                return

            lead = Lead(
                external_user_id=sender_id,
                platform=lead_platform,
                name=user_name,
                message=content,
                sales_rep_id=assigned_rep.id,
                ad_repr="Messenger",
                assigned_at=datetime.now(),
                last_active_at=datetime.now(),
                status="active"
            )
            db.add(lead)
            db.commit()
            log_action(f"🆕 New lead created for {user_name} and assigned to rep {assigned_rep.id}", actor_type="system", action_type="lead-created")
        else:
            lead.last_active_at = datetime.now()
            db.commit()
            log_action(f"👀 Existing lead {lead.id} updated last_active_at", actor_type="system", action_type="lead-touch")

        # 💬 Save message
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
        log_action(f"✅ Message saved for lead {lead.id}", actor_type="user", user_id=lead.id, action_type="message-save")

        # 🧠 Trigger meeting detection via Celery
        detect_meeting_intent.delay(lead.id, content)
        log_action(f"🧠 Celery task dispatched for lead {lead.id}", actor_type="system", action_type="meeting-intent")

        # 🔊 Emit new message to socket room
        if not lead.sales_rep or not lead.sales_rep.user:
    # 🧠 Find the company based on page_id and platform
            company_filter = {
                "messenger": Company.messenger_page_id == page_id,
                "instagram": Company.instagram_page_id == page_id
            }

            company = db.query(Company).filter(company_filter.get(lead_platform)).first()

            reassigned_rep = get_next_sales_rep(db, company.id) if company else None
            if reassigned_rep:
                lead.sales_rep_id = reassigned_rep.id
                db.commit()
                log_action(
                    f"✅ Lead {lead.id} reassigned to rep {reassigned_rep.id}",
                    actor_type="system",
                    action_type="lead-reassigned"
                )
            else:
                log_action(
                    f"❌ No sales reps available for reassignment. Lead {lead.id} remains unassigned.",
                    level="error",
                    actor_type="system",
                    action_type="reassign-failed"
                )
                return  # 💥 Cannot continue without a valid rep

        # ✅ Emit to socket after ensuring rep assignment
        room = f"user_{lead.sales_rep.user_id}"
        socketio.emit("new_message", {
            "lead_id": str(lead.id),
            "sender": "user",
            "content": content,
            "sender_name": lead.name,
            "message_type": message_type,
            "timestamp": datetime.now().strftime("%d %b %Y, %I:%M %p")
        }, to=room)
        log_action(f"📡 New message emitted to room {room}", actor_type="system", action_type="socket-emit")

        # 🔔 Save notification
        notification = Notification(
            sender_name=lead.name,
            platform=lead.platform,
            lead_id=lead.id
        )
        db.add(notification)
        db.commit()
        log_action(f"🔔 Notification created for lead {lead.id}", actor_type="system", action_type="notify")

        # 🔄 Update unread count
        unread_messages = db.query(LeadMessage).filter_by(
            lead_id=lead.id,
            sender="user",
            is_read=False
        ).all()

        socketio.emit("unread_update", {
            "lead_id": str(lead.id),
            "unread_count": len(unread_messages)
        }, to=room)
        log_action(f"🔁 Unread count emitted: {len(unread_messages)}", actor_type="system", action_type="unread-update")

    except Exception as e:
        db.rollback()
        log_action("❌ Error handling Messenger event", level="error", actor_type="system", exc_info=True)
    finally:
        db.close()
    # db.session.commit()
    # send_message(sender_id, f"Hi {user_name}, thanks for messaging us!")


def handle_instagram_event(event, page_id, lead_platform, content, message_type, access_token,instagram_id):
    sender_id = event["sender"]["id"]
    log_action(f"📥 Incoming Instagram message type: {message_type} from {sender_id}", actor_type="system", action_type="message-received")

    try:
        db_instance = current_app.extensions['sqlalchemy']
        db = db_instance.session

        # 🔍 Find company by page_id
        company = db.query(Company).filter(Company.instagram_page_id == page_id).first()
        if not company:
            log_action(f"❌ No company found for Instagram page_id: {page_id}", level="error", actor_type="system")
            return

        # 👤 Get sender name
        user_name = get_lead_name(sender_id, platform="instagram",access_token=access_token,instagram_id=instagram_id)
        if not user_name:
            log_action(f"⚠️ Could not fetch name for Instagram sender {sender_id}", level="warning", actor_type="system")
            return

        # 🔍 Check if lead exists
        lead = db.query(Lead).filter_by(external_user_id=sender_id).first()

        if not lead:
            # ➕ Create new lead
            assigned_rep = get_next_sales_rep(db, company.id)
            if not assigned_rep:
                log_action(f"⚠️ No sales reps available for company {company.name}", level="warning", actor_type="system")
                return

            lead = Lead(
                external_user_id=sender_id,
                platform=lead_platform,
                name=user_name,
                message=content,
                sales_rep_id=assigned_rep.id,
                ad_repr="Instagram",
                assigned_at=datetime.now(),
                last_active_at=datetime.now(),
                status="active"
            )
            db.add(lead)
            db.commit()
            log_action(f"🆕 New Instagram lead created and assigned to rep {assigned_rep.id}", actor_type="system", action_type="lead-created")
        else:
            # 🕒 Update activity
            lead.last_active_at = datetime.now()
            db.commit()
            log_action(f"👀 Instagram lead {lead.id} updated last_active_at", actor_type="system", action_type="lead-touch")

        # 💬 Save message
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
        log_action(f"✅ Message saved for lead {lead.id}", actor_type="user", user_id=lead.id, action_type="message-save")

        # 🧠 Intent detection
        detect_meeting_intent.delay(lead.id, content)
        log_action(f"🧠 Celery task dispatched for lead {lead.id}", actor_type="system", action_type="meeting-intent")

        # 🚨 Reassignment if rep deleted
        if not lead.sales_rep or not lead.sales_rep.user_id:
            reassigned_rep = get_next_sales_rep(db, company.id)
            if reassigned_rep:
                lead.sales_rep_id = reassigned_rep.id
                db.commit()
                log_action(
                    f"✅ Lead {lead.id} reassigned to rep {reassigned_rep.id}",
                    actor_type="system",
                    action_type="lead-reassigned"
                )
                room = f"user_{reassigned_rep.user_id}"
            else:
                log_action(
                    f"❌ No reps available to reassign Instagram lead {lead.id}",
                    level="error",
                    actor_type="system",
                    action_type="reassign-failed"
                )
                return
        else:
            room = f"user_{lead.sales_rep.user_id}"

        # 📡 Emit message to rep
        socketio.emit("new_message", {
            "lead_id": str(lead.id),
            "sender": "user",
            "content": content,
            "sender_name": lead.name,
            "message_type": message_type,
            "timestamp": datetime.now().strftime("%d %b %Y, %I:%M %p")
        }, to=room)
        log_action(f"📡 New message emitted to room {room}", actor_type="system", action_type="socket-emit")

        # 🔔 Notification
        notification = Notification(
            sender_name=lead.name,
            platform=lead.platform,
            lead_id=lead.id
        )
        db.add(notification)
        db.commit()
        log_action(f"🔔 Notification created for lead {lead.id}", actor_type="system", action_type="notify")

        # 🔄 Unread update
        unread_messages = db.query(LeadMessage).filter_by(
            lead_id=lead.id,
            sender="user",
            is_read=False
        ).all()

        socketio.emit("unread_update", {
            "lead_id": str(lead.id),
            "unread_count": len(unread_messages)
        }, to=room)
        log_action(f"🔁 Unread count emitted: {len(unread_messages)}", actor_type="system", action_type="unread-update")

    except Exception:
        db.rollback()
        log_action("❌ Error handling Instagram event", level="error", actor_type="system", exc_info=True)
    finally:
        db.close()