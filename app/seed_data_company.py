

from werkzeug.security import generate_password_hash
from app.models.models import User, ReminderPurpose,db

def safe_seed_data():
    # Seed admin user if not exists
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", password=generate_password_hash("123admin"),email="admin@gmail.com",is_admin=True)
        db.session.add(admin)


    # Seed reminder purposes if not exists
    for purpose in ["Meeting", "Follow-up"]:
        if not ReminderPurpose.query.filter_by(name=purpose).first():
            db.session.add(ReminderPurpose(name=purpose))

    db.session.commit()

def ensure_admin_user():
    try:
        admin_exists = db.session.query(User).filter_by(is_admin=True).first()
        if not admin_exists:
            admin_user = User(
                username="admin",
                email="admin@example.com",
                password=generate_password_hash("admin123"),
                is_admin=True
            )
            db.session.add(admin_user)
            db.session.commit()
            print("✅ Admin user created with default credentials.")
        else:
            print("✅ Admin user already exists.")
    finally:
        db.session.close()

