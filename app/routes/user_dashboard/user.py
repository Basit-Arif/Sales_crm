from flask import Flask,Blueprint,render_template,url_for,redirect,jsonify,request,flash,session,current_app
from app.routes.auth import login_required
from app.models.models import Lead,LeadMessage,SalesRep,Notification,Meeting,LeadComment
from app.models import db
from app.services.massenger_services import send_message
from sqlalchemy.orm import joinedload
from datetime import datetime,timedelta

from app import socketio

from pytz import timezone
import pytz

user_bp=Blueprint("user",__name__,url_prefix="/user")

@user_bp.route('/')
@login_required
def index():
    session_db = db.session
    try:
        user_id = session.get("user_id")
        sales_rep = session_db.query(SalesRep).filter_by(user_id=user_id).first()

        if not sales_rep:
            flash("Sales representative not found.", "error")
            return redirect(url_for("user.dashboard"))

        # Lead filtering logic
        days_range = request.args.get("date_range", default=0, type=int)
        filter_date = datetime.now().date() - timedelta(days=days_range) if days_range else datetime.now().date()

        today_leads = session_db.query(Lead).filter(
            Lead.sales_rep_id == sales_rep.id,
            Lead.assigned_at >= datetime(filter_date.year, filter_date.month, filter_date.day)
        ).all()

        total_leads = len(today_leads)
        converted_leads = sum(1 for lead in today_leads if lead.status == "converted")
        closed_leads = sum(1 for lead in today_leads if lead.status == "closed")

        # ✅ Filter meetings for today (rep's local day boundaries converted to UTC)
        rep_tz = timezone("Asia/Karachi")
        now_local = datetime.now(rep_tz)
        start_local = rep_tz.localize(datetime(now_local.year, now_local.month, now_local.day))
        end_local = start_local + timedelta(days=1)
        start_utc = start_local.astimezone(pytz.utc)
        end_utc = end_local.astimezone(pytz.utc)
        
        print("start_utc",start_utc)
        print("end_utc",end_utc)

        today_meetings = session_db.query(Meeting).options(
            joinedload(Meeting.lead)
        ).filter(
            Meeting.sales_rep_id == sales_rep.id,
            Meeting.meeting_time_utc >= start_utc,
            Meeting.meeting_time_utc < end_utc
        ).order_by(Meeting.meeting_time_utc.asc()).all()

        # ✅ Pending feedback logic
        latest_meeting = session_db.query(Meeting).filter_by(sales_rep_id=sales_rep.id).order_by(Meeting.created_at.desc()).first()
        rep_timezone = latest_meeting.rep_timezone if latest_meeting and latest_meeting.rep_timezone else "Asia/Karachi"
        rep_tz = pytz.timezone(rep_timezone)

        now_local = datetime.now(rep_tz)  # This is your local time (aware)
        now_utc_equivalent = now_local.astimezone(pytz.utc) 

        pending_feedback = session_db.query(Meeting).options(
            joinedload(Meeting.lead)
        ).filter(
            Meeting.sales_rep_id == sales_rep.id,
            Meeting.status == "confirmed",
            Meeting.notes == None,
            Meeting.meeting_time_utc < now_utc_equivalent
        ).order_by(Meeting.meeting_time_utc.desc()).all()

        # Step 2: Convert meeting times to rep timezone (for UI or later logic)
        for meeting in pending_feedback:
            rep_tz = pytz.timezone(meeting.rep_timezone or "Asia/Karachi")
            meeting.local_time = meeting.meeting_time_utc.astimezone(rep_tz)

    finally:
        session_db.close()

    return render_template(
        "user/user_dashboard.html",
        total_leads=total_leads,
        converted_leads=converted_leads,
        closed_leads=closed_leads,
        today_meetings=today_meetings,
        pending_feedback=pending_feedback,
        pytz=pytz
    )

@user_bp.route('/dashboard')
@login_required
def dashboard():
    session_db = db.session
    user_id = session.get("user_id")
    sales_rep = session_db.query(SalesRep).filter_by(user_id=user_id).first()
    platform = request.args.get("platform", "messenger").lower()

    if not sales_rep:
        return "SalesRep not found for this user", 403

    print("-------sales_rep_id", sales_rep.id)

    leads_query = session_db.query(Lead).options(joinedload(Lead.messages)).filter_by(sales_rep_id=sales_rep.id)

    # Filter by platform if provided
    if platform in ["messenger", "instagram"]:
        leads_query = leads_query.filter(Lead.platform == platform)

    leads = leads_query.all()

    # Build list of dictionaries to avoid DetachedInstanceError
    processed_leads = []
    for lead in leads:
        unread_count = sum(1 for msg in lead.messages if msg.sender == 'user' and not msg.is_read)
        processed_leads.append({
            'id': lead.id,
            'name': lead.name,
            'unread_count': unread_count,
            'status': lead.status.lower() if lead.status else 'active'
        })

    session_db.close()
    print("this is the platform name ")
    print(platform)

    return render_template(
        "user/massenger_chat.html",
        leads=processed_leads,
        selected_lead=None,
        messages=[],
        platform=platform  # 🟢 Pass platform to template for conditional rendering if needed
    )


@user_bp.route("/lead/<int:lead_id>")
@login_required
def view_chat(lead_id):
    session_db = db.session
    user_id = session["user_id"]
    platform = request.args.get("platform")

    # Check if the current user is admin
    is_admin = session.get("is_admin") 
    print("is_admin", is_admin)

    if is_admin:
        leads_query = session_db.query(Lead).options(joinedload(Lead.messages))\
            .filter_by(platform=platform).all()
    else:
        sales_rep = session_db.query(SalesRep).filter_by(user_id=user_id).first()
        if not sales_rep:
            return "SalesRep not found", 403

        leads_query = session_db.query(Lead).options(joinedload(Lead.messages))\
            .filter_by(sales_rep_id=sales_rep.id, platform=platform).all()

    processed_leads = []
    selected_lead_data = None
    selected_messages = []

    for lead in leads_query:
        unread_count = sum(1 for msg in lead.messages if msg.sender == 'user' and not msg.is_read)

        if lead.id == lead_id:
            read_ids = []
            for msg in lead.messages:
                if msg.sender == 'user' and not msg.is_read:
                    msg.is_read = True
                    msg.read_at = datetime.utcnow()
                    msg.status = 'read'
                    read_ids.append(msg.id)
            session_db.commit()

            if read_ids:
                socketio.emit("message_read", {"lead_id": lead.id, "read_ids": read_ids})

            selected_lead_data = {
                'id': lead.id,
                'name': lead.name,
                'status': lead.status.lower() if lead.status else 'active',
                'is_admin_override': getattr(lead, 'is_admin_override', False)
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

    session_db.close()
    template_base = "user/base_chat.html"

    return render_template(
        "user/massenger_chat.html",
        leads=processed_leads,
        selected_lead=selected_lead_data,
        messages=selected_messages,
        platform=platform,
        template_base=template_base
    )

import os
from werkzeug.utils import secure_filename
from flask import current_app
import mimetypes

@user_bp.route("/lead/<int:lead_id>/send", methods=["POST"])
@login_required
def send_message_to_lead(lead_id):
    session_db = db.session
    lead = session_db.query(Lead).filter_by(id=lead_id).first()

    if not lead:
        flash("❌ Lead not found.", "error")
        return redirect(url_for("user.dashboard"))

    platform = lead.platform.lower()

    # 🧠 Get access token from lead -> sales_rep -> company
    company = lead.sales_rep.company
    if not company:
        flash("❌ No company linked to this lead's sales rep.", "error")
        return redirect(url_for("user.dashboard"))

    access_token = None
    if platform == "messenger":
        access_token = company.messenger_access_token
    elif platform == "instagram":
        access_token = company.instagram_access_token

    if not access_token:
        flash(f"❌ No access token found for {platform} in company settings.", "error")
        return redirect(url_for("user.dashboard"))

    # 📝 Send text message
    text = request.form.get("message", "").strip()
    if text:
        status = send_message(
            psid=lead.external_user_id,
            text=text,
            lead_id=lead.id,
            access_token=access_token,
            message_type="text",
            platform=platform,
            
        )
        if status.status_code != 200:
            flash("⚠️ Failed to send text message.", status.text,)

    # 📎 Handle file attachment
    uploaded_file = request.files.get("file")
    if uploaded_file and uploaded_file.filename:
        filename = secure_filename(uploaded_file.filename)
        upload_path = os.path.join(current_app.root_path, "static", "uploads")
        os.makedirs(upload_path, exist_ok=True)
        file_path = os.path.join(upload_path, filename)
        uploaded_file.save(file_path)

        file_url = url_for("static", filename=f"uploads/{filename}", _external=True)
        mime_type, _ = mimetypes.guess_type(filename)
        message_type = "image" if mime_type and mime_type.startswith("image") else "file"

        status = send_message(
            psid=lead.external_user_id,
            text=file_url,
            lead_id=lead.id,
            access_token=access_token,
            message_type=message_type,
            platform=platform,
            
        )
        if status.status_code != 200:
            flash("⚠️ Failed to send attachment.", "error")
        lead_id = lead.id
        platform = lead.platform

    session_db.close()
    return redirect(url_for("user.view_chat", lead_id=lead_id, platform=platform))

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

        session_db = db.session
        lead = session_db.query(Lead).filter_by(id=lead_id).first()

        if not lead:
            flash("❌ Lead not found.", "error")
            return jsonify({"success": False, "message": "Lead not found."}), 404

        # Optional: check permissions (e.g., only admin can change if converted)
        if lead.status == "converted" and session.get("role") != "admin":
            # flash("⚠️ Permission denied to update a converted lead.", "error")
            return jsonify({"success": False, "message": "Permission denied."}), 403

        lead.status = new_status
        session_db.commit()
        flash(f"✅ Lead status updated to {new_status}.", "success")
        return jsonify({"success": True, "message": "Status updated."})

    except Exception as e:
        flash("❌ Server error during status update.", "error")
        return jsonify({"success": False, "message": "Server error."}), 500

@user_bp.route("/main_dashboard")
@login_required
def main_dashboard():
    session_db = db.session
    sales_rep_id = session.get("user_id")
    leads = session_db.query(Lead).filter_by(sales_rep_id=sales_rep_id).all()
    session_db.close()
    return render_template("user/base_chat.html", leads=leads, selected_lead=None, messages=[])

@user_bp.route("/retry-message/<int:message_id>", methods=["POST"])
@login_required
def retry_failed_message(message_id):
    try:
        db = current_app.extensions["sqlalchemy"].db
        session_db = db.session
        data = request.get_json()
        content = data.get("content")
        message_type = data.get("message_type")

        message = session_db.query(LeadMessage).filter_by(id=message_id).first()
        if not message:
            flash("⚠️ Message not found.", "error")
            return jsonify({"success": False, "message": "Message not found."})

        lead = session_db.query(Lead).filter_by(id=message.lead_id).first()
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
        session_db.commit()

        return jsonify({"success": True, "message": "Message resent."})

    except Exception as e:
        flash("❌ Retry failed due to a server error.", "error")
        print("❌ Retry error:", e)
        return jsonify({"success": False, "message": "Server error."})
    
@user_bp.route('/notifications/mark_read', methods=['POST'])
@login_required
def mark_notifications_read():
    session_db = db.session
    try:
       
        user_id = session.get("user_id") 

        notifications = session_db.query(Notification).join(Lead).join(SalesRep).filter(
            SalesRep.user_id == user_id,
            Notification.is_read == False
        ).all()

        for notif in notifications:
            notif.is_read = True

        session_db.commit()
        return jsonify(success=True)
    except Exception as e:
        session_db.rollback()
        print("Error in mark_notifications_read:", e)
        return jsonify(success=False, error=str(e)), 500
    finally:
        session_db.close()

@user_bp.route("/notifications/unread")
@login_required
def unread_notifications():
    session_db = db.session
    try:
        
        user_id = session.get("user_id")

        # 🔔 Unread Notifications
        notifications = session_db.query(Notification).join(Lead).join(SalesRep).filter(
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
        messenger_msg_count = session_db.query(LeadMessage).join(Lead).join(SalesRep).filter(
            SalesRep.user_id == user_id,
            LeadMessage.is_read == False,
            LeadMessage.sender == "user",
            Lead.platform == "messenger"
        ).count()

        instagram_msg_count = session_db.query(LeadMessage).join(Lead).join(SalesRep).filter(
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
        session_db.close()



@user_bp.route("/all-leads")
@login_required
def all_leads():
    session_db = db.session
    try:
        leads = session_db.query(Lead).order_by(Lead.id.desc()).all()
        return render_template("user/all_leads.html", leads=leads)
    finally:
        session_db.close()


@user_bp.route("/lead/<int:lead_id>/add-comment", methods=["POST"])
def add_lead_comment(lead_id):
    session_db = db.session
    try:
        content = request.form.get("content")

        if not content:
            flash("Comment cannot be empty.", "danger")
            return redirect(request.referrer)

        comment = LeadComment(
            lead_id=lead_id,
            content=content,
            summary_date=datetime.now(pytz.timezone("Asia/Karachi")),
            generated_by=session["role"],
        )
        session_db.add(comment)
        session_db.commit()

        flash("✅ Comment added successfully!", "success")
        return redirect(request.referrer)

    except Exception as e:
        session_db.rollback()
        print("❌ Error adding comment:", e)
        flash("❌ Something went wrong while adding the comment.", "danger")
        return redirect(request.referrer)
    finally:
        session_db.close()


@user_bp.route("/lead/<int:lead_id>/comments")
@login_required
def view_lead_comments(lead_id):
    session_db = db.session
    try:
        lead = session_db.query(Lead).filter_by(id=lead_id).first()
        if not lead:
            flash("❌ Lead not found.", "error")
            return redirect(url_for("user.dashboard"))

        comments = session_db.query(LeadComment).filter(
            LeadComment.lead_id == lead_id,
            LeadComment.generated_by.in_(["admin", "user", "sales_rep"])
        ).order_by(LeadComment.created_at.desc()).all()

        return render_template("user/view_lead_comments.html", lead=lead, comments=comments)
    finally:
        session_db.close()