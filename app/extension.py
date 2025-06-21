from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_migrate import Migrate
from flask_mail import Mail

mail = Mail()

db = SQLAlchemy()
socketio = SocketIO(cors_allowed_origins="*")
migrate = Migrate()