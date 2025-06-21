from celery import Celery
from app import create_app
import os
from dotenv import load_dotenv
load_dotenv()

celery = Celery("sales_crm", broker_url = os.getenv(
    "CELERY_BROKER_URL",
    "redis://localhost:6379/0"  # Default for local Mac development
)
)
celery.conf.timezone = 'UTC'
celery.conf.enable_utc = True

def make_celery(app):
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    # ✅ here you import tasks AFTER app context setup
    from app.services import task
    
    return celery