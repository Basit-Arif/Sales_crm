from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from flask import current_app
from app.models.models import User, SalesRep
from app.services.helper_function import generate_token, verify_token, send_reset_email
from app.log_config import log_action

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    db = current_app.extensions["sqlalchemy"].session
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        try:
            user = db.query(User).filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                session["user_id"] = user.id
                sales_rep = db.query(SalesRep).filter_by(user_id=session["user_id"]).first()
                session["sales_rep_id"] = sales_rep.id if sales_rep else None
                session["is_admin"] = user.is_admin
                session["role"] = "admin" if user.is_admin else "user"

                log_action(
                    message=f"User '{username}' logged in",
                    user_id=user.id,
                    actor_type="admin" if user.is_admin else "user",
                    action_type="login"
                )

                flash("✅ Login successful", "success")
                return redirect(url_for("admin.index") if user.is_admin else url_for("user.index"))
            else:
                log_action(
                    message=f"Failed login attempt for username: {username}",
                    actor_type="user",
                    action_type="login-fail"
                )
                flash("❌ Invalid credentials", "danger")
        except Exception:
            log_action("Error during login", level="error", exc_info=True, actor_type="system")
            flash("❌ An error occurred. Please try again.", "danger")

    return render_template("login/login.html")


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.form['email']
    try:
        user = User.query.filter_by(email=email).first()

        if user:
            token = generate_token(user.username)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            send_reset_email(user.email, reset_url)

            log_action(
                message=f"Password reset link sent to {user.email}",
                user_id=user.id,
                actor_type="user",
                action_type="password-reset-request"
            )

            flash("✅ A reset link has been sent to your email.", "success")
        else:
            log_action(
                message=f"Password reset attempted for non-existing email: {email}",
                actor_type="user",
                action_type="password-reset-fail"
            )
            flash("❌ Email not found. Please check and try again.", "danger")

    except Exception:
        log_action("Error in forgot password", level="error", exc_info=True, actor_type="system")
        flash("❌ Something went wrong. Please try again.", "danger")

    return redirect(url_for("auth.login"))


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    username = verify_token(token)
    if not username:
        log_action("Invalid or expired reset token", actor_type="user", action_type="password-reset-invalid")
        flash("❌ The reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.login"))

    db = current_app.extensions["sqlalchemy"].session
    user = db.query(User).filter_by(username=username).first()

    if request.method == 'POST':
        try:
            new_password = request.form["password"]
            user.password = generate_password_hash(new_password)
            db.commit()

            log_action(
                message=f"Password reset successfully for user '{user.username}'",
                user_id=user.id,
                actor_type="user",
                action_type="password-reset-success"
            )

            flash("✅ Password successfully updated.", "success")
            return redirect(url_for("auth.login"))
        except Exception:
            log_action("Error during password reset", level="error", exc_info=True, actor_type="system")
            flash("❌ Failed to reset password. Try again.", "danger")

    return render_template("login/reset_password.html")


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
    log_action(
        message=f"User ID {session.get('user_id')} logged out",
        user_id=session.get("user_id"),
        actor_type="admin" if session.get("is_admin") else "user",
        action_type="logout"
    )
    session.clear()
    flash("👋 You have been logged out.", "info")
    return redirect(url_for("auth.login"))