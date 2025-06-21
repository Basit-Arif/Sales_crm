from flask import current_app
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Message
from app.extension import mail  # Ensure this is lowercase if you're instantiating with `mail = Mail(app)`

def generate_token(username):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(username, salt="password-reset")

def verify_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        return serializer.loads(token, salt="password-reset", max_age=expiration)
    except Exception:
        return None

def send_reset_email(email, reset_url):
    msg = Message(
        subject="🔐 Reset Your Password",
        sender=current_app.config['MAIL_USERNAME'],  # ✅ Use sender from config
        recipients=[email],
    )
    msg.body = f"Hi,\n\nClick the link below to reset your password:\n{reset_url}\n\nThis link expires soon."
    print(f"Sending email to: {email}")
    print(f"Reset URL: {reset_url}")
    mail.send(msg)