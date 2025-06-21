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






meeting=Blueprint("meeting",__name__,url_prefix="/meeting")
def get_db():
    if 'db' not in g:
        g.db = db.session
    return g.db


@meeting.route('/')
def index():
    db = get_db()
    current_user_id = session.get("user_id")
    ip_address = request.remote_addr
    print(f"ip_address{ip_address}")


    # Get sales_rep from user_id
    sales_rep = db.query(SalesRep).filter_by(user_id=current_user_id).first()
    sales_rep_id = sales_rep.id if sales_rep else None

    meetings = db.query(Meeting).filter_by(sales_rep_id=sales_rep_id).all()
    leads = db.query(Lead).filter_by(sales_rep_id=sales_rep_id).all()
    return render_template("meetings/index.html", meetings=meetings, current_user_id=current_user_id, leads=leads,pytz=pytz)


# Route to update meeting status
@meeting.route('/update_status/<int:meeting_id>', methods=["POST"])
def update_status(meeting_id):
    db = get_db()
    try:
        new_status = request.form.get("status")
        print("this is status:", new_status)

        meeting = db.query(Meeting).filter_by(id=meeting_id).first()
        if not meeting:
            flash("Meeting not found", "danger")
            return redirect(url_for("meeting.index"))

        meeting.status = new_status
        meeting.updated_at = datetime.utcnow()

        # ✅ Only trigger if status is confirmed
        if new_status.lower() in ["confirmed", "confirm"]:
            now_utc = datetime.utcnow()

            # 🛡️ Ensure meeting_time_utc is timezone-aware
            meeting_time = meeting.meeting_time_utc

            if meeting_time.tzinfo is None:
                # Treat stored datetime as UTC if it's naive
                meeting_time = pytz.utc.localize(meeting_time)
            else:
                meeting_time = meeting_time.astimezone(pytz.utc)

            if meeting_time > pytz.utc.localize(now_utc):
                print("⏰ Scheduling pre-meeting reminders")
                response = schedule_pre_meeting_reminders(meeting.lead, meeting_time, db)
                print(response)
            else:
                print("⚠️ Meeting time already passed; skipping reminder.")

        db.commit()
        flash(f"Meeting {meeting_id} status updated to {new_status}", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error updating meeting: {str(e)}", "danger")
    finally:
        db.close()

    return redirect(url_for("meeting.index"))

# Route to create new meeting
@meeting.route('/create', methods=["POST"])
def create():
    db = get_db()
    try:
        user_id = session.get("user_id")
        sales_rep = db.query(SalesRep).filter_by(user_id=user_id).first()

        if not sales_rep:
            flash("SalesRep not found for this user", "danger")
            return redirect(url_for("meeting.index"))

        sales_rep_id = sales_rep.id
        lead_id = request.form.get("lead_id")
        date_str = request.form.get("meeting_date")         # e.g. "2025-08-22"
        time_str = request.form.get("meeting_time")         # e.g. "3:00 PM"
        client_timezone = request.form.get("client_timezone")  # e.g. "US/Pacific"
        original_message = request.form.get("original_message")

        try:
            local_tz = pytz.timezone(client_timezone)
            try:
                naive_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")  # 24-hour format
            except ValueError:
                naive_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M %p")  # 12-hour fallback
            local_dt = local_tz.localize(naive_dt)
            meeting_time_utc = local_dt.astimezone(pytz.utc)
        except Exception as e:
            flash(f"Invalid time or timezone: {e}", "danger")
            return redirect(url_for("meeting.index"))

        new_meeting = Meeting(
            sales_rep_id=sales_rep_id,
            lead_id=lead_id,
            meeting_time_utc=meeting_time_utc,
            client_timezone=client_timezone,
            rep_timezone="Asia/Karachi",  # You may pull this dynamically later
            original_message=original_message,
            detected_time_string=time_str,
            detected_date_string=date_str,
            status="pending",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_meeting)
        db.commit()
        flash("Meeting created successfully!", "success")
    except Exception as e:
        flash(f"Error creating meeting: {str(e)}", "danger")
    finally:
        db.close()
    return redirect(url_for("meeting.index"))

@meeting.route('/edit/<int:meeting_id>', methods=["GET", "POST"])
def edit(meeting_id):
    db = get_db()
    try:
        meeting = db.query(Meeting).filter_by(id=meeting_id).first()
        if request.method == "POST":
            date = request.form.get("meeting_date")
            time = request.form.get("meeting_time")
            original_message = request.form.get("original_message")

            # Convert to UTC using stored client timezone
            try:
                from pytz import timezone
                local_tz = timezone(meeting.client_timezone)
                try:
                    naive_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
                except ValueError:
                    naive_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %I:%M %p")
                local_dt = local_tz.localize(naive_dt)
                meeting.meeting_time_utc = local_dt.astimezone(pytz.utc)
            except Exception as e:
                flash(f"Invalid date/time format or timezone: {e}", "danger")
                return redirect(url_for("meeting.index"))

            # Update detected fields
            meeting.detected_time_string = time
            meeting.detected_date_string = date
            meeting.original_message = original_message

            db.commit()
            flash("Meeting updated successfully!", "success")
            return redirect(url_for("meeting.index"))

        # GET: load meeting edit modal context
        current_user_id = session.get("user_id")
        sales_rep = db.query(SalesRep).filter_by(user_id=current_user_id).first()
        leads = db.query(Lead).filter_by(sales_rep_id=sales_rep.id).all()
        return render_template("meetings/edit.html", meeting=meeting, leads=leads)
    except Exception as e:
        flash(f"Error editing meeting: {str(e)}", "danger")
        return redirect(url_for("meeting.index"))
    finally:
        db.close()


# Route to mark meeting as complete and optionally create a follow-up
@meeting.route("/complete/<int:meeting_id>", methods=["POST"])
def complete(meeting_id):
    db = get_db()
    try:
        meeting = db.query(Meeting).filter_by(id=meeting_id).first()
        if not meeting:
            flash("Meeting not found.", "danger")
            return redirect(url_for("meeting.index"))

        # Mark the meeting as completed
        meeting.status = "completed"
        meeting.notes = request.form.get("notes")
        meeting.updated_at = datetime.utcnow()

        # Optional follow-up
        followup_time_str = request.form.get("followup_time")
        if followup_time_str:
            followup_time = datetime.strptime(followup_time_str, "%Y-%m-%dT%H:%M")
            followup_meeting = Meeting(
                sales_rep_id=meeting.sales_rep_id,
                lead_id=meeting.lead_id,
                meeting_time=followup_time,
                original_message="Follow-up created after completion.",
                detected_time_string=followup_time_str,
                status="pending",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(followup_meeting)

        db.commit()
        flash("Meeting marked as completed.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error completing meeting: {e}", "danger")
    finally:
        db.close()

    return redirect(url_for("meeting.index"))



@meeting.route('/update_note/<int:meeting_id>', methods=["POST"])
def update_note(meeting_id):
    db = get_db()
    try:
        meeting = db.query(Meeting).filter_by(id=meeting_id).first()
        if meeting:
            meeting.notes = request.form.get("notes")
            meeting.updated_at = datetime.utcnow()
            db.commit()
            flash("Meeting note updated.", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error updating note: {str(e)}", "danger")
    finally:
        db.close()
    return redirect(url_for("user.index"))