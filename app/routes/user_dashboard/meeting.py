from flask import Flask,Blueprint,render_template,url_for,redirect,jsonify,request,flash,session



from app.database import SessionLocal
from app.models.models import Meeting, Lead, SalesRep
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from sqlalchemy import func

meeting=Blueprint("meeting",__name__,url_prefix="/meeting")
@meeting.route('/')
def index():
    db = SessionLocal()
    current_user_id = session.get("user_id")

    # Get sales_rep from user_id
    sales_rep = db.query(SalesRep).filter_by(user_id=current_user_id).first()
    sales_rep_id = sales_rep.id if sales_rep else None

    meetings = db.query(Meeting).filter_by(sales_rep_id=sales_rep_id).all()
    leads = db.query(Lead).filter_by(sales_rep_id=sales_rep_id).all()
    return render_template("meetings/index.html", meetings=meetings, current_user_id=current_user_id, leads=leads)


# Route to update meeting status
@meeting.route('/update_status/<int:meeting_id>', methods=["POST"])
def update_status(meeting_id):
    db = SessionLocal()
    try:
        new_status = request.form.get("status")
        meeting = db.query(Meeting).filter_by(id=meeting_id).first()
        if meeting:
            meeting.status = new_status
            meeting.updated_at = datetime.utcnow()
            db.commit()
            flash(f"Meeting {meeting_id} status updated to {new_status}", "success")
        else:
            flash("Meeting not found", "danger")
    except Exception as e:
        flash(f"Error updating meeting: {str(e)}", "danger")
    finally:
        db.close()
    return redirect(url_for("meeting.index"))

# Route to create new meeting
@meeting.route('/create', methods=["POST"])
def create():
    db = SessionLocal()
    try:
        user_id = session.get("user_id")
        sales_rep = db.query(SalesRep).filter_by(user_id=user_id).first()

        if not sales_rep:
            flash("SalesRep not found for this user", "danger")
            return redirect(url_for("meeting.index"))

        sales_rep_id = sales_rep.id
        lead_id = request.form.get("lead_id")
        meeting_time = request.form.get("meeting_time")
        original_message = request.form.get("original_message")

        new_meeting = Meeting(
            sales_rep_id=sales_rep_id,
            lead_id=lead_id,
            meeting_time=datetime.strptime(meeting_time, "%Y-%m-%dT%H:%M"),
            original_message=original_message,
            detected_time_string=meeting_time,
            status="pending",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
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
    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter_by(id=meeting_id).first()
        if request.method == "POST":
            date = request.form.get("meeting_date")
            time = request.form.get("meeting_time")
            ampm = request.form.get("ampm")
            meeting.meeting_time = datetime.strptime(f"{date} {time} {ampm}", "%Y-%m-%d %I:%M %p")
            meeting.original_message = request.form.get("original_message")
            meeting.detected_time_string = request.form.get("meeting_time")
            db.commit()
            flash("Meeting updated successfully!", "success")
            return redirect(url_for("meeting.index"))

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
    db = SessionLocal()
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
    db = SessionLocal()
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