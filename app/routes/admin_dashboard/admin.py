from flask import Flask,Blueprint,render_template,url_for,redirect,jsonify,request,flash,session
from app.database import SessionLocal
import random
from datetime import datetime,timedelta
from datetime import datetime as dt
from app.models.models import User, SalesRep, Company,Lead,Meeting,LeadMessage,LeadStatusHistory,LeadComment
import traceback
from werkzeug.security import generate_password_hash
from app.routes.auth import admin_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload



admin_bp=Blueprint("admin",__name__,url_prefix="/admin")

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




@admin_bp.route("/add-user", methods=["GET", "POST"])
def add_user():
    db = SessionLocal()

    if request.method == "POST":
        try:
            username = request.form["username"]
            raw_password = request.form["password"]
            is_admin = bool(request.form.get("is_admin"))
            hashed_password = generate_password_hash(raw_password)

            user = User(
                username=username,
                password=hashed_password,
                is_admin=is_admin
            )
            db.add(user)
            db.flush()  # Get user.id without committing yet

            if not is_admin:
                name = request.form.get("full_name")
                phone = request.form.get("phone_number")
                company_id = int(request.form.get("company_id"))
                code = f"REP{random.randint(1000, 9999)}"

                sales_rep = SalesRep(
                    code=code,
                    name=name,
                    phone_number=phone,
                    company_id=company_id,
                    user_id=user.id,
                    joined_at=datetime.utcnow()
                )
                db.add(sales_rep)

            db.commit()
            flash("✅ User created successfully.", "success")
            return redirect(url_for("admin.index"))

        except Exception as e:
            db.rollback()
            traceback.print_exc()
            flash(f"❌ Error: {str(e)}", "danger")
            return redirect(url_for("admin.add_user"))  # return after rollback
        finally:
            db.close()

    else:
        companies = db.query(Company).all()
        db.close()
        return render_template("admin/admin_add_user.html", companies=companies)
    
@admin_bp.route('/')
def index():
    return render_template('admin/base_admin.html')


@admin_bp.route('/dashboard')
def dashboard():
    db = SessionLocal()
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
                Meeting.meeting_time >= today,
                Meeting.meeting_time <= end_of_week
            )\
            .order_by(Meeting.meeting_time)\
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
                Meeting.meeting_time >= today,
                Meeting.meeting_time <= end_of_week
            )\
            .order_by(Meeting.meeting_time)\
            .limit(10).all()

        upcoming_meetings = [{
            "rep_name": m.rep_name,
            "lead_name": m.lead_name,
            "meeting_time": m.Meeting.meeting_time
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
        labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        leads_data = [5, 6, 3, 7, 4, 5, 6]
        messages_data = [10, 12, 8, 9, 11, 6, 7]

        return render_template(
            'admin/admin_dashboard.html',
            labels=labels,
            leads_data=leads_data,
            messages_data=messages_data,
            last_active_reps=last_active_reps,
            upcoming_meetings=upcoming_meetings,
            selected_company=company_filter
        )
    finally:
        db.close()

@admin_bp.route('/api/kpi_summary')
def api_kpi_summary():
    db = SessionLocal()
    try:
        company_filter = request.args.get("company", "all")
        today = datetime.utcnow().date()    

        if company_filter == 'all':
            total_leads = db.query(Lead).count()
            total_reps = db.query(SalesRep).count()
            meetings_today = db.query(Meeting).filter(func.date(Meeting.meeting_time) == today).count()
            overdue_followups = db.query(Lead).filter(
                Lead.status == 'active',
                Lead.last_active_at < datetime.utcnow() - timedelta(days=2)
            ).count()
        else:
            try:
                company_id = int(company_filter)
            except ValueError:
                return jsonify({"error": "Invalid company ID"}), 400

            total_leads = db.query(Lead).join(SalesRep).filter(SalesRep.company_id == company_id).count()
            total_reps = db.query(SalesRep).filter_by(company_id=company_id).count()
            meetings_today = db.query(Meeting).join(SalesRep).filter(
                SalesRep.company_id == company_id,
                func.date(Meeting.meeting_time) == today
            ).count()
            overdue_followups = db.query(Lead).join(SalesRep).filter(
                SalesRep.company_id == company_id,
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





@admin_bp.route("/leads/overview")
def leads_overview():
    db = SessionLocal()
    try:
        company_filter = request.args.get("company", "all")

        today = datetime.utcnow()
        inactive_threshold = today - timedelta(days=5)

        if company_filter == "all":
            leads = db.query(Lead).all()
        else:
            try:
                company_id = int(company_filter)
            except ValueError:
                return "Invalid company ID", 400

            leads = db.query(Lead).join(SalesRep).filter(SalesRep.company_id == company_id).all()

        # Update inactive leads
        for lead in leads:
            if lead.status.lower() != "inactive" and lead.last_active_at and lead.last_active_at < inactive_threshold:
                lead.status = "inactive"
                db.add(LeadStatusHistory(
                    lead_id=lead.id,
                    status="inactive",
                    changed_by=lead.sales_rep_id
                ))

        db.commit()

        # Reload updated leads (with filter again)
        leads_query = db.query(Lead).join(SalesRep)
        if company_filter != "all":
            leads_query = leads_query.filter(SalesRep.company_id == company_id)
        leads = leads_query.order_by(Lead.last_active_at.desc()).all()

        return render_template(
            "admin/lead_overview.html",
            leads=leads,
            selected_company=company_filter
        )

    finally:
        db.close()



@admin_bp.route('/leads/<int:lead_id>')
def lead_detail(lead_id):
    db = SessionLocal()
    try:
        # Load the lead with sales rep and company (if needed)
        lead = db.query(Lead)\
            .options(joinedload(Lead.sales_rep).joinedload(SalesRep.company))\
            .filter(Lead.id == lead_id).first()

        if not lead:
            return "Lead not found", 404

        # Get GPT-generated daily comment summaries for this lead
        comments = db.query(LeadComment)\
            .filter_by(lead_id=lead_id)\
            .order_by(LeadComment.summary_date.desc())\
            .all()

        return render_template("admin/lead_detail.html", lead=lead, comments=comments)

    finally:
        db.close()


@admin_bp.route('/leads/add-summary', methods=['POST'])
def add_lead_summary():
    db = SessionLocal()
    try:
        lead_id = request.form.get("lead_id")
        summary_date = request.form.get("summary_date")
        content = request.form.get("content")

        if not (lead_id and summary_date and content):
            flash("All fields are required.", "danger")
            return redirect(url_for("admin.lead_detail", lead_id=lead_id))

        # Prevent duplicate summary for same date
        existing = db.query(LeadComment).filter_by(
            lead_id=lead_id,
            summary_date=summary_date
        ).first()

        if existing:
            flash("A summary for this date already exists.", "warning")
            return redirect(url_for("admin.lead_detail", lead_id=lead_id))

        comment = LeadComment(
            lead_id=lead_id,
            summary_date=summary_date,
            content=content,
            generated_by="admin"
        )
        db.add(comment)
        db.commit()
        flash("Summary added successfully.", "success")
        return redirect(url_for("admin.lead_detail", lead_id=lead_id))

    except Exception as e:
        db.rollback()
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for("admin.lead_detail", lead_id=lead_id))

    finally:
        db.close()


@admin_bp.route("/salesrep/overview")
def salesrep_overview():
    db = SessionLocal()
    try:
        company_filter = request.args.get("company", "all")
        status_filter = request.args.get("status")
        from_date_raw = request.args.get("from_date",datetime.now().strftime("%Y-%m-%d"))
        to_date_raw = request.args.get("to_date",datetime.now().strftime("%Y-%m-%d"))
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

            meeting_query = db.query(Meeting).filter_by(sales_rep_id=rep.id, status="confirmed")
            if from_dt:
                meeting_query = meeting_query.filter(Meeting.meeting_time >= from_dt)
            if to_dt:
                meeting_query = meeting_query.filter(Meeting.meeting_time <= to_dt)
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
                "last_active": last_msg,
                "status": current_status
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
    db = SessionLocal()
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