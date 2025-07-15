from flask import Flask,Blueprint,render_template,url_for,redirect,jsonify,request,flash,session,g
from flask import current_app

from app.models.models import Meeting, Lead, SalesRep
from app.models import db
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from sqlalchemy import func
import pytz
from flask import request
from app.services.meeting import schedule_pre_meeting_reminders
from app import db 
from app.routes.user_dashboard import user_bp
from app.routes.auth import login_required
from app.routes.user_dashboard import socketio
from sqlalchemy.orm import joinedload


@user_bp.route("/all-leads")
@login_required
def all_leads():
    session_db = db.session
    try:
        leads = session_db.query(Lead).order_by(Lead.id.desc()).all()
        return render_template("user/all_leads.html", leads=leads)
    finally:
        session_db.close()



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



