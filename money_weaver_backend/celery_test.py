import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.services.celery_app import celery_app
from src.tasks.video_tasks import generate_assembler_video_task

if __name__ == '__main__':
    # Check Celery configuration
    print("Broker URL:", celery_app.conf.broker_url)
    print("Registered tasks:", list(celery_app.tasks.keys()))
    
    # Send task
    result = generate_assembler_video_task.apply_async(args=[1, "Test prompt"])
    print(f"Task ID: {result.id}")
    print("Task sent to queue")
    
    # Check task status
    print("Task state:", result.state)