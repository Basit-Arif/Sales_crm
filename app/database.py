from app.models import db

# Optional seed or init logic
def init_db(app):
    db.init_app(app)