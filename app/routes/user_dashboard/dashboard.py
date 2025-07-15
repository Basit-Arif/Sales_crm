from app.routes.user_dashboard import user_bp
from app.routes.auth import login_required
from app.models import db
from app.models.models import Lead, SalesRep, Meeting
from flask import render_template, url_for, redirect, request, flash, session
from datetime import datetime, timedelta
import pytz
from pytz import timezone
from sqlalchemy.orm import joinedload


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

