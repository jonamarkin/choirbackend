from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'choirbackend.settings')

app = Celery('choirbackend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()