from . import admin_bp
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime, timedelta
from sqlalchemy import func
from app.models.models import SalesRep, Lead, Meeting, LeadMessage
from app.routes.admin_dashboard import get_db
from app.routes.auth import admin_required
import pytz


@admin_bp.route("/salesrep/overview")
def salesrep_overview():
    db = get_db()
    try:
        company_filter = request.args.get("company", "all")
        status_filter = request.args.get("status")
        from_date_raw = request.args.get("from_date", datetime.now().strftime("%Y-%m-%d"))
        to_date_raw = request.args.get("to_date", datetime.now().strftime("%Y-%m-%d"))
        query = request.args.get("q", "").lower()

        from_dt = datetime.strptime(from_date_raw, "%Y-%m-%d") if from_date_raw else None
        to_dt = datetime.strptime(to_date_raw, "%Y-%m-%d") if to_date_raw else None

        idle_threshold = datetime.utcnow() - timedelta(minutes=30)

        # Base query
        sales_reps_query = db.query(SalesRep)

        if company_filter != "all":
            try:
                company_id = int(company_filter)
                sales_reps_query = sales_reps_query.filter_by(company_id=company_id)
            except ValueError:
                return "Invalid company ID", 400

        if query:
            sales_reps_query = sales_reps_query.filter(func.lower(SalesRep.name).like(f"%{query}%"))

        sales_reps = sales_reps_query.all()

        reps = []
        for rep in sales_reps:
            lead_query = db.query(Lead).filter_by(sales_rep_id=rep.id)
            if from_dt:
                lead_query = lead_query.filter(Lead.assigned_at >= from_dt)
            if to_dt:
                lead_query = lead_query.filter(Lead.assigned_at <= to_dt)
            leads = lead_query.all()
            total_leads = len(leads)

            converted_leads_query = db.query(Lead).filter_by(sales_rep_id=rep.id, status="converted")
            if from_dt:
                converted_leads_query = converted_leads_query.filter(Lead.assigned_at >= from_dt)
            if to_dt:
                converted_leads_query = converted_leads_query.filter(Lead.assigned_at <= to_dt)
            converted_leads_query = converted_leads_query.count()

            # Meeting count filters should use meeting_time_utc and rep's local timezone
            meeting_query = db.query(Meeting).filter_by(sales_rep_id=rep.id, status="confirmed")

            # Try to get a timezone from the latest meeting
            rep_timezone = "Asia/Karachi"
            latest_meeting = db.query(Meeting).filter_by(sales_rep_id=rep.id).order_by(Meeting.created_at.desc()).first()
            if latest_meeting and latest_meeting.rep_timezone:
                rep_timezone = latest_meeting.rep_timezone

            tz = pytz.timezone(rep_timezone)
            if from_dt:
                from_dt_utc = tz.localize(from_dt).astimezone(pytz.utc)
                meeting_query = meeting_query.filter(Meeting.meeting_time_utc >= from_dt_utc)
            if to_dt:
                to_dt_utc = tz.localize(to_dt + timedelta(days=1)).astimezone(pytz.utc)
                meeting_query = meeting_query.filter(Meeting.meeting_time_utc < to_dt_utc)

            meeting_count = meeting_query.count()

            

            last_msg = db.query(func.max(LeadMessage.timestamp))\
                .join(Lead, Lead.id == LeadMessage.lead_id)\
                .filter(Lead.sales_rep_id == rep.id).scalar()

            current_status = "Active" if last_msg and last_msg > idle_threshold else "Idle"

            # Apply status filter after calculating
            if status_filter and current_status.lower() != status_filter.lower():
                continue
            

            reps.append({
                "name": rep.name,
                "company_name": rep.company.name if rep.company else "N/A",
                "total_leads": total_leads,
                "converted_leads_query": converted_leads_query,
                "meetings": meeting_count,
                "confirmed_meetings": meeting_count,  # same as 'meetings'
                "last_active": last_msg,
                "status": current_status
                # Optionally add "local_meeting_times": local_meeting_times
            })

        return render_template(
            "admin/salesrep_overview.html",
            reps=reps,
            selected_company=company_filter
        )

    finally:
        db.close()



@admin_bp.route('/salesrep/<int:rep_id>')
def salesrep_detail(rep_id):
    db = get_db()
    try:
        rep = db.query(SalesRep).filter_by(id=rep_id).first()
        if not rep:
            return "Sales rep not found", 404

        total_leads = db.query(Lead).filter_by(sales_rep_id=rep.id).count()
        qualified = db.query(Lead).filter_by(sales_rep_id=rep.id, status="Qualified").count()

        confirmed_meetings = db.query(Meeting).join(Lead).filter(
            Meeting.sales_rep_id == rep.id,
            Meeting.status == "confirmed"
        ).order_by(Meeting.meeting_time.desc()).limit(10).all()

        last_msg = db.query(func.max(LeadMessage.timestamp))\
            .join(Lead, Lead.id == LeadMessage.lead_id)\
            .filter(Lead.sales_rep_id == rep.id).scalar()

        last_message = last_msg.strftime("%b %d, %I:%M %p") if last_msg else "N/A"

        recent_leads = db.query(Lead)\
            .filter_by(sales_rep_id=rep.id)\
            .order_by(Lead.assigned_at.desc())\
            .limit(10).all()

        kpi = {
            "total_leads": total_leads,
            "qualified": qualified,
            "meetings": len(confirmed_meetings),
            "last_message": last_message
        }

        return render_template(
            "admin/salesrep_details.html",
            rep=rep,
            kpi=kpi,
            confirmed_meetings=[{
                "lead_name": m.lead.name,
                "meeting_time": m.meeting_time
            } for m in confirmed_meetings],
            recent_leads=recent_leads
        )
    finally:
        db.close()