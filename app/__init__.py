from flask import Flask,session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.sql import text
from app.config import Config
from app.models.models import Base
from flask_socketio import SocketIO
from app.database import init_db
from flask_wtf.csrf import generate_csrf
from app.database import SessionLocal
from app.models.models import User, SalesRep, Company,Lead,Meeting



# ✅ Global instance
socketio = SocketIO(cors_allowed_origins="*")


def create_app():
    app = Flask(__name__)
   
    app.secret_key = 'basitarif234'
    app.config.from_object(Config)

    # ✅ Don’t redeclare, just init it
    socketio.init_app(app)

    with app.app_context():
        init_db()
        from app.routes.massenger import massenger_bp
        from app.routes.webhook import webhook_bp
        from app.routes.user_dashboard.user import user_bp
        from app.routes.admin_dashboard.admin import admin_bp
        from app.routes.auth import auth_bp
        from app.routes.user_dashboard.meeting import meeting

        app.register_blueprint(massenger_bp)
        app.register_blueprint(webhook_bp)
        app.register_blueprint(user_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(auth_bp)
        app.register_blueprint(meeting)
        
        @app.context_processor
        def inject_csrf_token():
            return dict(csrf_token=generate_csrf())
        @app.context_processor
        def inject_companies():
            if "user_id" in session and session.get("is_admin"):
                db = SessionLocal()
                try:
                    companies = db.query(Company).order_by(Company.name).all()
                    return {'companies': companies}
                finally:
                    db.close()
            return {'companies': []}

    return app

# ✅ Expose for run.py
__all__ = ['socketio', 'create_app']
