from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.sql import text
from app.config import Config
from app.models.models import Base
from flask_socketio import SocketIO
from app.database import init_db
from flask_wtf.csrf import generate_csrf



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
        from app.routes.admin_dashboard.admin import admin
        from app.routes.auth import auth_bp

        app.register_blueprint(massenger_bp)
        app.register_blueprint(webhook_bp)
        app.register_blueprint(user_bp)
        app.register_blueprint(admin)
        app.register_blueprint(auth_bp)
        @app.context_processor
        def inject_csrf_token():
            return dict(csrf_token=generate_csrf())

    return app

# ✅ Expose for run.py
__all__ = ['socketio', 'create_app']
