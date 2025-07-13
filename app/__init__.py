from flask import Flask, session, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.sql import text
from flask_socketio import SocketIO
from flask_wtf.csrf import generate_csrf
from app.extension import db, migrate, socketio, mail
from app.models.models import User, Company
from app.seed_data_company import safe_seed_data
from app.config import Config
import os
from dotenv import load_dotenv

# ✅ Global SocketIO instance
socketio = SocketIO(cors_allowed_origins="*")

def get_db():
    if 'db' not in g:
        g.db = db.session
    return g.db

def create_app(config_class=Config):
    """Application factory with auto-migrate, auto-seed, and Celery-safe config."""
    load_dotenv()
    app = Flask(__name__)
    app.secret_key = 'basitarif234'
    app.config.from_object(config_class)

    # ✅ Mail Config
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

    # ✅ Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)
    mail.init_app(app)

    with app.app_context():
        
        # ✅ Register Blueprints
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

        # ✅ Auto-upgrade + seed if not Celery
        
        
        print("🔗 Connected to DB:", app.config["SQLALCHEMY_DATABASE_URI"])

        env = os.environ.get("FLASK_ENV", "").lower()
        print(f"🌐 ENV: {env}")

        if env in ["test"]:
            from flask_migrate import upgrade
            
            print("🧪 Running in test mode. Skipping migrations and seeding."
                " Use `pytest` to run tests.")
            return app

            

        if env in ["development", "production"]:
            user_count = db.session.query(User).count()
            if user_count == 0:
                print(f"🌱 Seeding initial data in {env}...")
                safe_seed_data()
            else:
                print(f"✅ Data already exists. Skipping seed in {env}.")

        # ✅ Context Processors
        @app.context_processor
        def inject_csrf_token():
            return dict(csrf_token=generate_csrf())

        @app.context_processor
        def inject_companies():
            if "user_id" in session and session.get("is_admin"):
                companies = db.session.query(Company).order_by(Company.name).all()
                print("🔍 Injected Companies:", [c.name for c in companies])
                return {'companies': companies}
            return {'companies': []}

    @app.teardown_appcontext
    def teardown_db(exception=None):
        db_session = g.pop("db", None)
        if db_session is not None:
            db_session.close()

    return app

__all__ = ['socketio', 'create_app']