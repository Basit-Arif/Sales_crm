from flask import Flask,Blueprint,render_template,url_for,redirect,jsonify,request,flash,session,g
from flask import current_app

from app.models.models import Meeting, Lead, SalesRep,LeadComment
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

