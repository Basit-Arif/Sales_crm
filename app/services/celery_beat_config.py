from celery import Celery
from celery.schedules import crontab

app = Celery('tasks', broker='redis://localhost:6379/0')

# Load your task module
app.autodiscover_tasks(['app.services.task'])

# Schedule to run every 30 minutes
app.conf.beat_schedule = {
    'check-meeting-reminders-every-30min': {
        'task': 'app.services.task.check_meeting_notes_due',
        'schedule': crontab(minute='*/30'),
    },
}

app.conf.timezone = 'Asia/Karachi'