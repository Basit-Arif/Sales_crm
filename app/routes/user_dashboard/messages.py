from app.routes.user_dashboard import user_bp, socketio, jsonify
from app.routes.auth import login_required
from app.models import db
from app.models.models import Lead, SalesRep, Meeting, LeadMessage
from flask import render_template, url_for, redirect, request, flash, session, current_app
from datetime import datetime, timedelta
import pytz
from pytz import timezone
from sqlalchemy.orm import joinedload
import os
from werkzeug.utils import secure_filename
import mimetypes
from app.log_config import log_action  # ✅ make sure this import is valid
from sqlalchemy.exc import OperationalError
from app.log_config import log_exceptions

@user_bp.route("/lead/<int:lead_id>/send", methods=["POST"])
@log_exceptions("send_message_to_lead")
@login_required
def send_message_to_lead(lead_id):
    session_db = db.session
    lead = session_db.query(Lead).filter_by(id=lead_id).first()

    if not lead:
        flash("❌ Lead not found.", "error")
        return redirect(url_for("user.dashboard"))

    platform = lead.platform.lower()
    company = lead.sales_rep.company

    if not company:
        flash("❌ No company linked to this lead's sales rep.", "error")
        return redirect(url_for("user.dashboard"))

    access_token = company.messenger_access_token if platform == "messenger" else company.instagram_access_token

    if not access_token:
        flash(f"❌ No access token found for {platform} in company settings.", "error")
        return redirect(url_for("user.dashboard"))

    text = request.form.get("message", "").strip()
    if text:
        try:
            from app.services.massenger_services import create_pending_message
            from app.services.task import async_send_message

            message_id = create_pending_message(
                psid=lead.external_user_id,
                text=text,
                lead_id=lead.id,
                message_type="text",
                platform=platform
            )
            async_send_message.delay(
                message_id=message_id,
                psid=lead.external_user_id,
                text=text,
                access_token=access_token,
                message_type="text",
                platform=platform
            )
            log_action(f"📤 Message queued to {platform} lead {lead.id}", user_id=session.get("user_id"))
        except Exception as e:
            log_action("❌ Error sending message", level="error", user_id=session.get("user_id"), exc_info=True)

    uploaded_file = request.files.get("file")
    if uploaded_file and uploaded_file.filename:
        try:
            from app.services.massenger_services import create_pending_message
            from app.services.task import async_upload_and_send_file

            filename = secure_filename(uploaded_file.filename)
            content_type = uploaded_file.content_type
            file_content = uploaded_file.read()

            message_type = "image" if content_type.startswith("image") else "file"
            message_id = create_pending_message(
                psid=lead.external_user_id,
                text="",
                lead_id=lead.id,
                message_type=message_type,
                platform=platform
            )

            async_upload_and_send_file.delay(
                message_id=message_id,
                file_name=filename,
                file_content=file_content,
                content_type=content_type,
                bucket_name="crmceobucket",
                platform=platform,
                psid=lead.external_user_id,
                access_token=access_token
            )

            log_action(f"📎 File upload queued for {lead.id} by user {session.get('user_id')}", user_id=session.get("user_id"))

            socketio.emit("new_message", {
                "lead_id": lead.id,
                "sender_name": session.get("username"),
                "platform": platform,
                "message": {
                    "id": message_id,
                    "content": text,
                    "sender": "sales_rep",
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_type": "text",
                    "status": "pending"
                }
            }, room=f"lead_{lead.id}")

            return jsonify({"success": True, "message": "✅ Attachment is being sent...", "message_id": message_id})

        except Exception as e:
            log_action("❌ Failed to upload and send attachment", level="error", exc_info=True)
            return jsonify({"success": False, "error": f"❌ S3 upload failed: {str(e)}"}), 500

    session_db.close()
    return jsonify({"success": True, "message": "✅ Message is being sent."})


@user_bp.route("/lead/<int:lead_id>/update-status", methods=["POST"])
@login_required
def update_lead_status(lead_id):
    try:
        data = request.get_json(force=True)
        new_status = data.get("status")

        if new_status not in ["active", "converted", "closed"]:
            log_action(f"❌ Invalid status: {new_status}", level="error")
            return jsonify({"success": False, "message": "Invalid status."}), 400

        session_db = db.session
        lead = session_db.query(Lead).filter_by(id=lead_id).first()

        if not lead:
            log_action(f"❌ Lead {lead_id} not found", level="error")
            return jsonify({"success": False, "message": "Lead not found."}), 404

        if lead.status == "converted" and session.get("role") != "admin":
            log_action(f"🚫 Unauthorized status change for lead {lead_id}", level="error")
            return jsonify({"success": False, "message": "Permission denied."}), 403

        lead.status = new_status
        session_db.commit()
        log_action(f"✅ Lead {lead_id} status updated to {new_status}", user_id=session.get("user_id"))
        return jsonify({"success": True, "message": "Status updated."})

    except Exception as e:
        log_action("❌ Error updating lead status", level="error", exc_info=True)
        return jsonify({"success": False, "message": "Server error."}), 500


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
            log_action(f"⚠️ Message {message_id} not found", level="error")
            return jsonify({"success": False, "message": "Message not found."})

        lead = session_db.query(Lead).filter_by(id=message.lead_id).first()
        if not lead:
            log_action(f"⚠️ Lead not found for message {message_id}", level="error")
            return jsonify({"success": False, "message": "Lead not found."})

        from app.services.massenger_services import send_message
        response_data = send_message(psid=lead.external_user_id, text=content, lead_id=lead.id, message_type=message_type)

        message.status = "sent"
        message.timestamp = datetime.utcnow()
        if response_data and isinstance(response_data, dict):
            message.platform_message_id = response_data.get("message_id")
        session_db.commit()

        log_action(f"🔁 Message {message_id} resent successfully", user_id=session.get("user_id"))
        return jsonify({"success": True, "message": "Message resent."})

    except Exception as e:
        log_action("❌ Error retrying message", level="error", exc_info=True)
        return jsonify({"success": False, "message": "Server error."})

    