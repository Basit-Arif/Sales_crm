from . import admin_bp
from flask import render_template, request, session, redirect, url_for, current_app, flash, jsonify
from app.models.models import Meeting, SalesRep, Lead, LeadMessage
from app.services.utils import convert_utc_to_timezone
from . import get_db
from sqlalchemy import func
from datetime import datetime, timedelta

@admin_bp.route('/dashboard')
def dashboard():
    db = get_db()
    try:
        company_filter = request.args.get('company')
        if company_filter:
            session["selected_company"] = company_filter
        else:
            company_filter = session.get("selected_company", "all")

        today = datetime.utcnow().date()
        end_of_week = today + timedelta(days=2)

        # Upcoming meetings query
        if company_filter == 'all':
            upcoming_meetings_raw = db.query(
                Meeting,
                SalesRep.name.label("rep_name"),
                Lead.name.label("lead_name")
            ).select_from(Meeting)\
            .join(SalesRep, SalesRep.id == Meeting.sales_rep_id)\
            .join(Lead, Lead.id == Meeting.lead_id)\
            .filter(
                Meeting.status == "confirmed",
                Meeting.meeting_time_utc >= today,
                Meeting.meeting_time_utc <= end_of_week
            )\
            .order_by(Meeting.meeting_time_utc)\
            .limit(10).all()
        else:
            company_id = int(company_filter)
            upcoming_meetings_raw = db.query(
                Meeting,
                SalesRep.name.label("rep_name"),
                Lead.name.label("lead_name")
            ).select_from(Meeting)\
            .join(SalesRep, SalesRep.id == Meeting.sales_rep_id)\
            .join(Lead, Lead.id == Meeting.lead_id)\
            .filter(
                Meeting.status == "confirmed",
                SalesRep.company_id == company_id,
                Meeting.meeting_time_utc >= today,
                Meeting.meeting_time_utc <= end_of_week
            )\
            .order_by(Meeting.meeting_time_utc)\
            .limit(10).all()

        upcoming_meetings = [{
            "rep_name": m.rep_name,
            "lead_name": m.lead_name,
            "meeting_time": convert_utc_to_timezone(m.Meeting.meeting_time_utc, m.Meeting.rep_timezone or "Asia/Karachi"),
            "timezone": m.Meeting.rep_timezone or "Asia/Karachi"
        } for m in upcoming_meetings_raw]

        # --- Last Active Reps Section ---
        from sqlalchemy.orm import aliased
        LM = aliased(LeadMessage)

        latest_msg_subq = (
            db.query(
                SalesRep.id.label("rep_id"),
                func.max(LeadMessage.timestamp).label("last_active")
            )
            .join(Lead, Lead.sales_rep_id == SalesRep.id)
            .join(LeadMessage, Lead.id == LeadMessage.lead_id)
            .group_by(SalesRep.id)
        ).subquery()

        last_active_raw = (
            db.query(
                SalesRep.name,
                Lead.name.label("client"),
                LM.timestamp.label("last_active")
            )
            .join(Lead, Lead.sales_rep_id == SalesRep.id)
            .join(LM, LM.lead_id == Lead.id)
            .join(latest_msg_subq, (latest_msg_subq.c.rep_id == SalesRep.id) & (latest_msg_subq.c.last_active == LM.timestamp))
            .order_by(LM.timestamp.desc())
            .limit(5)
            .all()
        )

        last_active_reps = [
            {"name": r.name, "last_active": r.last_active, "client": r.client}
            for r in last_active_raw
        ]
    
        # Dummy chart data
       
        import pytz
        from collections import Counter
       

        # Define timezone
        pakistan_tz = pytz.timezone("Asia/Karachi")

        # Get today's date in Pakistan time
        today = datetime.now().date()

        # Last 7 days (from today)
        last_7_days = [today - timedelta(days=i) for i in reversed(range(7))]

        # Fetch leads created in the last 7 days
        lead_rows = db.query(Lead.assigned_at).filter(
            Lead.assigned_at >= datetime.now() - timedelta(days=7)
        ).all()

        # Fetch messages sent in the last 7 days
        message_rows = db.query(LeadMessage.timestamp).filter(
            LeadMessage.timestamp >= datetime.utcnow() - timedelta(days=7)
        ).all()

        # Group by day in Asia/Karachi timezone
        def group_by_local_day(timestamps):
            day_counter = Counter()
            for ts in timestamps:
                if ts[0]:  # handle null values
                    local_day = ts[0].astimezone(pakistan_tz).date()
                    day_counter[local_day] += 1
            return day_counter

        lead_dict = group_by_local_day(lead_rows)
        message_dict = group_by_local_day(message_rows)

        # Format chart data
        labels = [day.strftime('%a') for day in last_7_days]
        leads_data = [lead_dict.get(day, 0) for day in last_7_days]
        messages_data = [message_dict.get(day, 0) for day in last_7_days]

        lead_dict = group_by_local_day(lead_rows)
        message_dict = group_by_local_day(message_rows)

        # Final values
        labels = [day.strftime('%a') for day in last_7_days]
        leads_data = [lead_dict.get(day, 0) for day in last_7_days]
        messages_data = [message_dict.get(day, 0) for day in last_7_days]
        platform_counts = (
            db.query(Lead.platform, func.count(Lead.id))
            .filter(Lead.platform.in_(['messenger', 'instagram']))
            .group_by(Lead.platform)
            .all()
        )

        pie_labels = []
        pie_data = []
        platform_map = {"messenger": "Messenger", "instagram": "Instagram"}

        for platform_code, count in platform_counts:
            pie_labels.append(platform_map.get(platform_code, "Other"))
            pie_data.append(count)

        return render_template(
            'admin/admin_dashboard.html',
            labels=labels,
            leads_data=leads_data,
            messages_data=messages_data,
            last_active_reps=last_active_reps,
            upcoming_meetings=upcoming_meetings,
            selected_company=company_filter,
            pie_labels=pie_labels,
            pie_data=pie_data
        )
    finally:
        db.close()


@admin_bp.route('/api/kpi_summary')
def api_kpi_summary():
    from datetime import datetime
    import pytz
    db = get_db()
    try:
        company_filter = request.args.get("company")
        today_utc = datetime.now()

        if company_filter == 'all':
            total_leads = db.query(Lead).count()
            total_reps = db.query(SalesRep).count()
            confirmed_meetings = db.query(Meeting).filter(Meeting.status == "confirmed").all()
        else:
            try:
                company_id = int(company_filter)
            except ValueError:
                return jsonify({"error": "Invalid company ID"}), 400

            total_leads = db.query(Lead).join(SalesRep).filter(SalesRep.company_id == company_id).count()
            total_reps = db.query(SalesRep).filter_by(company_id=company_id).count()
            confirmed_meetings = db.query(Meeting).join(SalesRep).filter(
                SalesRep.company_id == company_id,
                Meeting.status == "confirmed"
            ).all()

        # Count meetings that occur today in each rep's local time
        meetings_today = 0
        for m in confirmed_meetings:
            try:
                rep_tz = pytz.timezone(m.rep_timezone or "Asia/Karachi")
                local_today = datetime.now(rep_tz).date()
                local_meeting_date = m.meeting_time_utc.astimezone(rep_tz).date()
                if local_meeting_date == local_today:
                    meetings_today += 1
            except Exception:
                continue  # skip any with bad timezone

        # Overdue follow-up remains unchanged
        overdue_followups = db.query(Lead).join(SalesRep).filter(
            (True if company_filter == 'all' else SalesRep.company_id == company_id),
            Lead.status == 'active',
            Lead.last_active_at < datetime.utcnow() - timedelta(days=2)
        ).count()

        return jsonify({
            "total_leads": total_leads,
            "total_reps": total_reps,
            "meetings_today": meetings_today,
            "overdue_followups": overdue_followups
        })

    finally:
        db.close()



