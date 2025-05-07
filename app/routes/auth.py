from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from werkzeug.security import check_password_hash
from app.database import SessionLocal
from app.models.models import User

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    db = SessionLocal()
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = db.query(User).filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["is_admin"] = user.is_admin
            flash("✅ Login successful", "success")
            return redirect(url_for("admin.index") if user.is_admin else url_for("user.index"))
        else:
            flash("❌ Invalid credentials", "danger")
    return render_template("login/login.html")





def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("❌ Please log in first.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    
    return decorated_function
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            flash("❌ Admin access required.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("👋 You have been logged out.", "info")
    return redirect(url_for("auth.login"))