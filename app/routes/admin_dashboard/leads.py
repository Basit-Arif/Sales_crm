from . import admin_bp
from flask import render_template, request, redirect, url_for, flash, g
from app.models.models import Lead, LeadComment, SalesRep, LeadMessage, LeadStatusHistory
from app.routes.admin_dashboard import get_db
from app.services.task import summarize_leads_for_date
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
import traceback
import markdown
from markupsafe import Markup
from sqlalchemy import func

@admin_bp.route("/leads/overview")
def leads_overview():
    
    db = get_db()
    try:
        company_filter = request.args.get("company", "all")
        today = datetime.now()
        summary_date = today.date()
        inactive_threshold = today - timedelta(days=5)

        # Filter leads based on company
        if company_filter == "all":
            leads = db.query(Lead).all()
        else:
            try:
                company_id = int(company_filter)
                leads = db.query(Lead).join(SalesRep).filter(SalesRep.company_id == company_id).all()
            except ValueError:
                return "Invalid company ID", 400

        # Collect data to minimize repeated DB queries
        from collections import defaultdict
        lead_ids = [lead.id for lead in leads]
        comment_map = defaultdict(list)
        for c in (
            db.query(LeadComment)
            .filter(LeadComment.lead_id.in_(lead_ids),
                    LeadComment.generated_by == "gpt")
            .all()
        ):
            key = (c.lead_id, c.summary_date.date() if isinstance(c.summary_date, datetime) else c.summary_date)
            comment_map[key].append(c)

        latest_msg_map = {
            r.lead_id: r.latest_time for r in db.query(
                LeadMessage.lead_id,
                func.max(LeadMessage.timestamp).label("latest_time")
            ).filter(LeadMessage.lead_id.in_(lead_ids))
            .group_by(LeadMessage.lead_id)
            .all()
        }

        # Process each lead
        for lead in leads:
            # Update inactive
            if lead.status.lower() != "inactive" and lead.last_active_at and lead.last_active_at < inactive_threshold:
                lead.status = "inactive"
                db.add(LeadStatusHistory(
                    lead_id=lead.id,
                    status="inactive",
                    changed_by=lead.sales_rep_id
                ))

            latest_msg_time = latest_msg_map.get(lead.id)
            print(latest_msg_time)

            # Match comments for the same summary date, but compare by exact datetime
            last_active_date = latest_msg_time.date() if latest_msg_time else None
            latest_comment_list = comment_map.get((lead.id, last_active_date), [])
            filtered_comments = [
                c for c in latest_comment_list
                if c.created_at and latest_msg_time and c.created_at > latest_msg_time
            ]
            latest_comment = filtered_comments[-1] if filtered_comments else None

            print(f"the latest comment is {filtered_comments} and the last_active_date is {last_active_date}")

            # Trigger summary only if no GPT comment exists after latest message
            if latest_msg_time and not filtered_comments:
                print(f"🔁 Triggering summary for lead {lead.id} on {last_active_date}")
                # Ensure last_active_date is a datetime.date, not a str
                if isinstance(last_active_date, str):
                    last_active_date = datetime.strptime(last_active_date, "%Y-%m-%d").date()
                summarize_leads_for_date.delay(lead.id, str(last_active_date))

            # Attach comment to lead for UI
            lead.comment = latest_comment.content if latest_comment else None
            lead.comment_html = Markup(markdown.markdown(lead.comment)) if lead.comment else ""
            lead.has_new_message_after_summary = bool(
                latest_msg_time and (
                    not latest_comment or latest_msg_time > latest_comment.created_at
                )
            )

        db.commit()

        return render_template(
            "admin/lead_overview.html",
            leads=leads,
            selected_company=company_filter
        )

    except Exception as e:
        print(f"error int this leads overview {e}")
        traceback.print_exc()
        return "Server Error", 500
    finally:
        db.close()



@admin_bp.route('/leads/<int:lead_id>')
def lead_detail(lead_id):
    db = get_db()
    try:
        lead = db.query(Lead)\
            .options(joinedload(Lead.sales_rep).joinedload(SalesRep.company))\
            .filter(Lead.id == lead_id).first()

        if not lead:
            return "Lead not found", 404

        comments = (
            db.query(LeadComment)
            .filter(
                LeadComment.lead_id == lead_id,
                LeadComment.generated_by.in_(["admin", "user", "sales_rep", "gpt"])
            )
            .order_by(LeadComment.summary_date.desc(), LeadComment.created_at.desc())
            .all()
        )

        for comment in comments:
            comment.content_html = Markup(markdown.markdown(comment.content)) if comment.content else ""

        # Fetch all sales reps from the same company as this lead
        sales_reps = []
        if lead.sales_rep and lead.sales_rep.company:
            sales_reps = db.query(SalesRep)\
                .filter(SalesRep.company_id == lead.sales_rep.company_id)\
                .all()

        return render_template("admin/lead_detail.html", lead=lead, comments=comments, sales_reps=sales_reps)

    finally:
        db.close()


@admin_bp.route('/leads/add-summary', methods=['POST'])
def add_lead_summary():
    db = get_db()
    try:
        lead_id = request.form.get("lead_id")
        summary_date = request.form.get("summary_date")
        content = request.form.get("content")

        if not (lead_id and summary_date and content):
            flash("All fields are required.", "danger")
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