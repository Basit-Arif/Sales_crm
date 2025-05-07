from flask import Flask,Blueprint,render_template,url_for,redirect,jsonify,request,flash,session
from app.routes.auth import login_required
from app.database import SessionLocal
from app.models.models import Lead,LeadMessage,SalesRep,Notification
from app.services.massenger_services import send_message
from sqlalchemy.orm import joinedload
from datetime import datetime,timedelta

from app import socketio



user_bp=Blueprint("user",__name__,url_prefix="/user")

@user_bp.route('/')
@login_required
def index():
    db = SessionLocal()
    user_id = session.get("user_id")
    sales_rep = db.query(SalesRep).filter_by(user_id=user_id).first()

    if not sales_rep:
        flash("Sales representative not found.", "error")
        db.close()
        return redirect(url_for("user.dashboard"))

    # Get range from query param
    days_range = request.args.get("date_range", default=0, type=int)
    filter_date = datetime.utcnow().date() - timedelta(days=days_range) if days_range else datetime.utcnow().date()

    today_leads = db.query(Lead).filter(
        Lead.sales_rep_id == sales_rep.id,
        Lead.assigned_at >= datetime(filter_date.year, filter_date.month, filter_date.day)
    ).all()
    
    total_leads = len(today_leads)
    converted_leads = sum(1 for lead in today_leads if lead.status == "converted")
    closed_leads = sum(1 for lead in today_leads if lead.status == "closed")
    print("total_leads",total_leads)
    db.close()
    return render_template(
        "user/user_dashboard.html",
        total_leads=total_leads,
        converted_leads=converted_leads,
        closed_leads=closed_leads
    )

@user_bp.route('/dashboard')
@login_required
def dashboard():
    db = SessionLocal()
    user_id = session.get("user_id")
    sales_rep_id = db.query(SalesRep).filter_by(user_id=user_id).first()

    if not sales_rep_id:
        return "SalesRep not found for this user", 403

    
    print("-------sales_rep_id",sales_rep_id.id)

    leads = db.query(Lead).options(joinedload(Lead.messages)).filter_by(sales_rep_id=sales_rep_id.id).all()

    # Build list of dictionaries to avoid DetachedInstanceError
    processed_leads = []
    for lead in leads:
        unread_count = sum(1 for msg in lead.messages if msg.sender == 'user' and not msg.is_read)
        processed_leads.append({
            'id': lead.id,
            'name': lead.name,
            'unread_count': unread_count,
            'status': lead.status.lower() if lead.status else 'active'  # 🟢 add status here
        })

    db.close()

    return render_template(
        "user/massenger_chat.html",
        leads=processed_leads,
        selected_lead=None,
        messages=[]
    )



@user_bp.route("/lead/<int:lead_id>")
@login_required
def view_chat(lead_id):
    db = SessionLocal()
    user_id = session["user_id"]
    sales_rep_id = db.query(SalesRep).filter_by(user_id=user_id).first()

    # Preload all leads for sidebar
    leads_query = db.query(Lead).options(joinedload(Lead.messages)).filter_by(sales_rep_id=sales_rep_id.id).all()

    # Pre-process sidebar leads
    processed_leads = []
    selected_lead_data = None
    selected_messages = []

    for lead in leads_query:
        unread_count = sum(1 for msg in lead.messages if msg.sender == 'user' and not msg.is_read)

        if lead.id == lead_id:
            # mark user messages as read
            read_ids = []
            for msg in lead.messages:
                if msg.sender == 'user' and not msg.is_read:
                    msg.is_read = True
                    msg.read_at = datetime.utcnow()
                    msg.status = 'read'
                    read_ids.append(msg.id)
            db.commit()

            if read_ids:
                socketio.emit("message_read", {
                    "lead_id": lead.id,
                    "read_ids": read_ids
                })

            selected_lead_data = {
                'id': lead.id,
                'name': lead.name,
                'status': lead.status.lower() if lead.status else 'active'
            }

            selected_messages = [
                {
                    'id': msg.id,
                    'sender': msg.sender,
                    'content': msg.content,
                    'message_type': getattr(msg, 'message_type', 'text'),
                    'timestamp': msg.timestamp,
                    'status': msg.status
                }
                for msg in lead.messages
            ]

        processed_leads.append({
            'id': lead.id,
            'name': lead.name,
            'unread_count': unread_count,
            'status': lead.status.lower() if lead.status else 'active'
        })

    db.close()

    return render_template(
        "user/massenger_chat.html",
        leads=processed_leads,
        selected_lead=selected_lead_data,
        messages=selected_messages
    )



import os
from werkzeug.utils import secure_filename
from flask import current_app
import mimetypes

@user_bp.route("/lead/<int:lead_id>/send", methods=["POST"])
@login_required
def send_message_to_lead(lead_id):
    db = SessionLocal()
    selected_lead = db.query(Lead).filter_by(id=lead_id).first()

    if selected_lead:
        text = request.form.get("message", "").strip()
        if text:
            status = send_message(
                psid=selected_lead.external_user_id,
                text=text,
                lead_id=lead_id,
                message_type="text"
            )

            if status.status_code != 200:
                print(f"❌ Failed to send message to {selected_lead.external_user_id}. Status Code: {status}")
                flash("⚠️ Message failed to send. Please try again.", "error")

        uploaded_file = request.files.get("file")
        if uploaded_file and uploaded_file.filename != "":
            filename = secure_filename(uploaded_file.filename)
            upload_folder = os.path.join(current_app.root_path, "static", "uploads")
            os.makedirs(upload_folder, exist_ok=True)
            filepath = os.path.join(upload_folder, filename)
            uploaded_file.save(filepath)

            file_url = url_for("static", filename=f"uploads/{filename}", _external=True)
            mime_type, _ = mimetypes.guess_type(filename)
            message_type = "image" if mime_type and mime_type.startswith("image") else "file"

            status = send_message(
                psid=selected_lead.external_user_id,
                text=file_url,
                lead_id=lead_id,
                message_type=message_type
            )

            if status != 200:
                flash("⚠️ File failed to send.", "error")

    db.close()
    return redirect(url_for("user.view_chat", lead_id=lead_id))

@user_bp.route("/lead/<int:lead_id>/update-status", methods=["POST"])
@login_required
def update_lead_status(lead_id):
    try:
        data = request.get_json(force=True)
        print("🔄 Incoming status update payload:", data)

        new_status = data.get("status")
        print("✅ Parsed new_status:", new_status)

        if new_status not in ["active", "converted", "closed"]:
            flash(f"❌ Invalid status '{new_status}' received.", "error")
            return jsonify({"success": False, "message": "Invalid status."}), 400

        db = SessionLocal()
        lead = db.query(Lead).filter_by(id=lead_id).first()

        if not lead:
            flash("❌ Lead not found.", "error")
            return jsonify({"success": False, "message": "Lead not found."}), 404

        # Optional: check permissions (e.g., only admin can change if converted)
        if lead.status == "converted" and session.get("role") != "admin":
            # flash("⚠️ Permission denied to update a converted lead.", "error")
            return jsonify({"success": False, "message": "Permission denied."}), 403

        lead.status = new_status
        db.commit()
        flash(f"✅ Lead status updated to {new_status}.", "success")
        return jsonify({"success": True, "message": "Status updated."})

    except Exception as e:
        flash("❌ Server error during status update.", "error")
        return jsonify({"success": False, "message": "Server error."}), 500

@user_bp.route("/main_dashboard")
@login_required
def main_dashboard():
    db = SessionLocal()
    sales_rep_id = session.get("user_id")
    leads = db.query(Lead).filter_by(sales_rep_id=sales_rep_id).all()
    db.close()
    return render_template("user/base_chat.html", leads=leads, selected_lead=None, messages=[])

@user_bp.route("/retry-message/<int:message_id>", methods=["POST"])
@login_required
def retry_failed_message(message_id):
    try:
        db = SessionLocal()
        data = request.get_json()
        content = data.get("content")
        message_type = data.get("message_type")

        message = db.query(LeadMessage).filter_by(id=message_id).first()
        if not message:
            flash("⚠️ Message not found.", "error")
            return jsonify({"success": False, "message": "Message not found."})

        lead = db.query(Lead).filter_by(id=message.lead_id).first()
        if not lead:
            flash("⚠️ Lead not found.", "error")
            return jsonify({"success": False, "message": "Lead not found."})

        # Re-send the message and capture response (platform_message_id, etc.)
        from app.services.massenger_services import send_message
        response_data = send_message(psid=lead.external_user_id, text=content, lead_id=lead.id, message_type=message_type)

        # Update existing message with platform_message_id and new status
        message.status = "sent"
        message.timestamp = datetime.utcnow()
        if response_data and isinstance(response_data, dict):
            message.platform_message_id = response_data.get("message_id")
        db.commit()

        return jsonify({"success": True, "message": "Message resent."})

    except Exception as e:
        flash("❌ Retry failed due to a server error.", "error")
        print("❌ Retry error:", e)
        return jsonify({"success": False, "message": "Server error."})
    
@user_bp.route('/notifications/mark_read', methods=['POST'])
@login_required
def mark_notifications_read():
    db = SessionLocal()
    try:
       
        user_id = session.get("user_id") 

        notifications = db.query(Notification).join(Lead).join(SalesRep).filter(
            SalesRep.user_id == user_id,
            Notification.is_read == False
        ).all()

        for notif in notifications:
            notif.is_read = True

        db.commit()
        return jsonify(success=True)
    except Exception as e:
        db.rollback()
        print("Error in mark_notifications_read:", e)
        return jsonify(success=False, error=str(e)), 500
    finally:
        db.close()

@user_bp.route("/notifications/unread")
@login_required
def unread_notifications():
    db = SessionLocal()
    try:
        user_id = session.get("user_id")

        # 🔔 Unread Notifications
        notifications = db.query(Notification).join(Lead).join(SalesRep).filter(
            SalesRep.user_id == user_id,
            Notification.is_read == False
        ).all()

        notification_data = [
            {
                "sender_name": n.sender_name,
                "platform": n.platform,
                "time": n.created_at.strftime("%I:%M %p")
            } for n in notifications
        ]

        # 💬 Unread Messages (used for Live Messaging badge)
        messenger_msg_count = db.query(LeadMessage).join(Lead).join(SalesRep).filter(
            SalesRep.user_id == user_id,
            LeadMessage.is_read == False,
            LeadMessage.sender == "user",
            Lead.platform == "messenger"
        ).count()

        instagram_msg_count = db.query(LeadMessage).join(Lead).join(SalesRep).filter(
            SalesRep.user_id == user_id,
            LeadMessage.is_read == False,
            LeadMessage.sender == "user",
            Lead.platform == "instagram"
        ).count()

        return jsonify({
            "notifications": notification_data,
            "notification_count": len(notifications),
            "messenger_unread_messages": messenger_msg_count,
            "instagram_unread_messages": instagram_msg_count
        })

    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        db.close()
