import sys
import os
import json
import redis
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.services.celery_app import celery_app

if __name__ == '__main__':
    # Get the Celery producer
    producer = celery_app.producer_pool.acquire(block=True, timeout=10)
    
    try:
        # Create a task message
        task_message = {
            'task': 'src.tasks.video_tasks.generate_assembler_video_task',
            'id': 'test-task-002',
            'args': [1, 'Test prompt from direct producer'],
            'kwargs': {},
            'retries': 0,
            'eta': None,
            'expires': None,
        }
        
        # Send the task
        producer.publish(
            body=task_message,
            exchange='celery',
            routing_key='celery',
            retry=False,
        )
        
        print("Task sent using Celery producer")
    finally:
        celery_app.producer_pool.release(producer)