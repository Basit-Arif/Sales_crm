from app import create_app
from app.celery_app import make_celery
from app.log_config import setup_logging
setup_logging()

app = create_app()
celery = make_celery(app)

# Import your tasks AFTER app & celery are initialized
from app.services import task