from app.routes.admin_dashboard import admin_bp
from flask import render_template, request, redirect, url_for, flash, session
from app.models.models import User, SalesRep, Company
from werkzeug.security import generate_password_hash
from app.routes.admin_dashboard import get_db
import random
import traceback
from datetime import datetime
from app.routes.auth import admin_required
import pytz
from sqlalchemy.orm import joinedload


@admin_bp.route("/add-user", methods=["GET", "POST"])
def add_user():
    db = get_db()

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
    


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    db = get_db()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        sales_rep = db.query(SalesRep).filter_by(user_id=user_id).first()

        if request.method == "POST":
            user.email = request.form.get("email")
            user.username = request.form.get("username")
            is_active = request.form.get("is_active") == "on"

            if sales_rep:
                sales_rep.phone_number = request.form.get("phone_number")
                sales_rep.active = is_active
                sales_rep.status = "active" if is_active else "inactive"
                sales_rep.status_updated_at = datetime.now(pytz.utc)

            db.commit()
            flash("✅ User updated successfully.", "success")
            return redirect(url_for("admin.manage_users"))

        return render_template("admin/edit_user.html", user=user, sales_rep=sales_rep)

    except Exception as e:
        db.rollback()
        flash(f"❌ Error updating user: {str(e)}", "danger")
        return redirect(url_for("admin.dashboard"))
    finally:
        db.close()

@admin_bp.route("/users")
def manage_users():
    db = get_db()
    try:
        users = db.query(User).outerjoin(SalesRep).options(joinedload(User.sales_rep)).all()
        return render_template("admin/manage_user.html", users=users)
    finally:
        db.close()