from flask import Flask,Blueprint,render_template,url_for,redirect,jsonify,request,flash,session
from app.database import SessionLocal
import random
from datetime import datetime
from app.models.models import User, SalesRep, Company
import traceback
from werkzeug.security import generate_password_hash
from app.routes.auth import admin_required


admin=Blueprint("admin",__name__,url_prefix="/admin")

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

@admin.route("/")
def index():
    return render_template("admin/admin_dashboard.html")


@admin.route("/add-user", methods=["GET", "POST"])
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