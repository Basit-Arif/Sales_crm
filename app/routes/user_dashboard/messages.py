

from app.routes.user_dashboard import user_bp,socketio,jsonify
from app.routes.auth import login_required
from app.models import db
from app.models.models import Lead, SalesRep, Meeting,LeadMessage
from flask import render_template, url_for, redirect, request, flash, session
from datetime import datetime, timedelta
import pytz
from pytz import timezone
from sqlalchemy.orm import joinedload
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
    lead_id = lead.id


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
        from app.services.massenger_services import create_pending_message
        message_id = create_pending_message(
            psid=lead.external_user_id,
            text=text,
            lead_id=lead.id,
            message_type="text",
            platform=platform
        )
        from app.services.task import async_send_message

        async_send_message.delay(
            message_id=message_id,
            psid=lead.external_user_id,
            text=text,
            access_token=access_token,
            message_type="text",
            platform=platform
        )
        

    # 📎 Handle file attachment
    import boto3
    from botocore.exceptions import NoCredentialsError
    import os
    import mimetypes
    from werkzeug.utils import secure_filename

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    uploaded_file = request.files.get("file")
    if uploaded_file and uploaded_file.filename:
        try:
            from app.services.massenger_services import create_pending_message
            from app.services.task import async_upload_and_send_file  # ✅ Correct import path

            filename = secure_filename(uploaded_file.filename)
            content_type = uploaded_file.content_type
            file_content = uploaded_file.read()

            # Determine message type
            message_type = "image" if content_type.startswith("image") else "file"

            # Create a pending message in DB
            message_id = create_pending_message(
                psid=lead.external_user_id,
                text="",  # To be updated after S3 upload
                lead_id=lead.id,
                message_type=message_type,
                platform=platform,
            )

            # Queue Celery task for upload + send
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
            try:
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
            except e:
                print("❌ Error emitting new_message event:", e)
            return jsonify({"success": True, "message": "✅ Attachment is being sent...", "message_id": message_id})

        except NoCredentialsError:
            return jsonify({"success": False, "error": "❌ AWS credentials not found. Cannot upload file."}), 400

        except Exception as e:
            return jsonify({"success": False, "error": f"❌ S3 upload failed: {str(e)}"}), 500

    session_db.close()
    return jsonify({"success": True, "message": "✅ Message is being sent."})



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