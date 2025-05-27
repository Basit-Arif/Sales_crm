from flask import Flask,session, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.sql import text
from app.config import Config
from flask_socketio import SocketIO
from app.models import db
from flask_wtf.csrf import generate_csrf




from app.models.models import User, SalesRep, Company,Lead,Meeting

# Register Flask-Migrate
migrate = Migrate()


def get_db():
    if 'db' not in g:
        g.db = db.session
    return g.db


# ✅ Global instance
socketio = SocketIO(cors_allowed_origins="*")


def create_app():
    app = Flask(__name__)
   
    app.secret_key = 'basitarif234'
    app.config.from_object(Config)

    db.init_app(app)
    socketio.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        from app.routes.massenger import massenger_bp
        from app.routes.webhook import webhook_bp
        from app.routes.user_dashboard.user import user_bp
        from app.routes.admin_dashboard.admin import admin_bp
        from app.routes.auth import auth_bp
        from app.routes.user_dashboard.meeting import meeting
        from app.celery_worker import init_celery
        
        init_celery(app)
        app.register_blueprint(massenger_bp)
        app.register_blueprint(webhook_bp)
        app.register_blueprint(user_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(auth_bp)
        app.register_blueprint(meeting)
        

        from flask_migrate import upgrade
        import os

        # ✅ Auto-upgrade the database if running locally
        if os.environ.get("FLASK_ENV") == "development":
            try:
                upgrade()
                print("🔄 Database auto-upgraded via Flask-Migrate")
            except Exception as e:
                print("⚠️ Failed to auto-upgrade the database:", str(e))
        
        @app.context_processor
        def inject_csrf_token():
            return dict(csrf_token=generate_csrf())
        
        @app.context_processor
        def inject_companies():
            if "user_id" in session and session.get("is_admin"):
                companies = db.session.query(Company).order_by(Company.name).all()
                print("🔍 Injected Companies:", [c.name for c in companies])  # Debug print
                return {'companies': companies}
            return {'companies': []}

    @app.teardown_appcontext
    def teardown_db(exception=None):
        db_session = g.pop("db", None)
        if db_session is not None:
            db_session.close()
        
    

    return app

# ✅ Expose for run.py
__all__ = ['socketio', 'create_app']
