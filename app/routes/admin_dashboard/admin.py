from flask import Flask, Blueprint, render_template, url_for, redirect, jsonify, request, flash, session, current_app, g
import random
from datetime import datetime, timedelta
from datetime import datetime as dt
from app.models.models import User, SalesRep, Company,Lead,Meeting,LeadMessage,LeadStatusHistory,LeadComment
import traceback
from werkzeug.security import generate_password_hash
from app.routes.auth import admin_required
from werkzeug.security import check_password_hash
from sqlalchemy import func
from sqlalchemy.orm import joinedload
import pytz
from celery import current_app
import markdown
from markupsafe import Markup
from app import db  # Add this if not already present
from app.services.utils import convert_utc_to_timezone
from app.services.task import summarize_leads_for_date
from app import db  # or just import your app if it's already initialized
from . import admin_bp  # Assuming you have a blueprint named admin_bp

from . import get_db


# --- DB session management using Flask g ---


@admin_bp.teardown_app_request
def teardown_db(exception=None):
    db_session = g.pop('db', None)
    if db_session is not None:
        db_session.close()



# @admin.before_request
# def restrict_to_admins():
#     # If user is not logged in at all
#     if "user_id" not in session:
#         flash("❌ Please log in first.", "danger")
#         return redirect(url_for("auth.login"))

#     # If user is logged in but not admin
#     if not session.get("is_admin"):
#         flash("⚡ Only admins can access the admin dashboard.", "danger")
#         return redirect(url_for("user.index"))



    
@admin_bp.route('/')
def index():
    print("Session after login:", dict(session))

    if not session.get("is_admin"):
        flash("⚠️ Access restricted to admins only.", "danger")
        return redirect(url_for("user.index"))

    return render_template('admin/base_admin.html')


@admin_bp.route("/test-companies")
def test_companies():
    db = get_db()
    companies = db.query(Company).all()
    return jsonify([{"id": c.id, "name": c.name} for c in companies])



@admin_bp.route('/transfer-lead', methods=['POST'])
def transfer_leads():
    db = get_db()
    try:
        lead_id = request.form.get("lead_id")
        new_sales_rep_id = request.form.get("new_sales_rep_id")

        if not lead_id or not new_sales_rep_id:
            flash("❌ Missing lead or sales rep.", "danger")
            return redirect(request.referrer or url_for("admin.lead_overview"))

        lead = db.query(Lead).filter_by(id=lead_id).first()
        new_rep = db.query(SalesRep).filter_by(id=new_sales_rep_id).first()

        if not lead or not new_rep:
            flash("❌ Lead or sales rep not found.", "danger")
            return redirect(request.referrer or url_for("admin.lead_overview"))

        lead.sales_rep_id = new_rep.id
        db.commit()

        flash(f"✅ Lead '{lead.name}' successfully transferred to {new_rep.name}.", "success")
        return redirect(url_for("admin.lead_detail", lead_id=lead.id))

    except Exception as e:
        db.rollback()
        print("❌ Error transferring lead:", e)
        flash("❌ Something went wrong. Transfer failed.", "danger")
        return redirect(request.referrer or url_for("admin.lead_overview"))

    finally:
        db.close()

    





@admin_bp.route("/leads/<int:lead_id>/conversation")
def lead_conversation(lead_id):
    db = get_db()
    try:
        lead = db.query(Lead).filter_by(id=lead_id).first()
        if not lead:
            return "Lead not found", 404

        messages = db.query(LeadMessage)\
            .filter_by(lead_id=lead_id)\
            .order_by(LeadMessage.timestamp.asc())\
            .all()

        return render_template("admin/lead_conversation.html", lead=lead, messages=messages)
    finally:
        db.close()