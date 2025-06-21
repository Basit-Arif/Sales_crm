from app import create_app
from app.celery_app import make_celery

app = create_app()
celery = make_celery(app)

# Import your tasks AFTER app & celery are initialized
from app.services import task