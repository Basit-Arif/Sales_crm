

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

