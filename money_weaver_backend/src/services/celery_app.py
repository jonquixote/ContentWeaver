from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

# Create Celery instance
celery_app = Celery('money_weaver')

# Configuration
celery_app.conf.update(
    broker_url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'src.tasks.video_tasks.*': {'queue': 'video_generation'},
    },
    task_annotations={
        '*': {'rate_limit': '10/s'}
    }
)

# Auto-discover tasks
celery_app.autodiscover_tasks(['src.tasks'])

# Explicitly import tasks to ensure they're registered
import src.tasks.video_tasks

if __name__ == '__main__':
    celery_app.start()

