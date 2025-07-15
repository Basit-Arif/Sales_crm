from flask import Flask,Blueprint,render_template,url_for,redirect,jsonify,request,flash,session,current_app
from app.routes.auth import login_required
from app.models.models import Lead,LeadMessage,SalesRep,Notification,Meeting,LeadComment
from app.models import db
from app.services.massenger_services import send_message
from sqlalchemy.orm import joinedload
from datetime import datetime,timedelta
from app.routes.user_dashboard import user_bp

from app import socketio

from pytz import timezone
import pytz



@user_bp.route("/main_dashboard")
@login_required
def main_dashboard():
    session_db = db.session
    sales_rep_id = session.get("user_id")
    leads = session_db.query(Lead).filter_by(sales_rep_id=sales_rep_id).all()
    session_db.close()
    return render_template("user/base_chat.html", leads=leads, selected_lead=None, messages=[])


@user_bp.route("/api/message/<int:message_id>")
@login_required
def get_message_content(message_id):
    message = db.session.query(LeadMessage).filter_by(id=message_id).first()
    if not message:
        return {"error": "Message not found"}, 404

    return {
        "id": message.id,
        "content": message.content,
        "message_type": message.message_type
    }