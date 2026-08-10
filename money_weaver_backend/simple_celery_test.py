import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from celery import Celery

# Create a simple Celery app for testing
test_app = Celery('test')
test_app.conf.update(
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0',
)

@test_app.task(name='simple_celery_test.simple_task')
def simple_task():
    return "Task completed successfully"

if __name__ == '__main__':
    # Send task
    result = simple_task.delay()
    print(f"Task ID: {result.id}")
    print("Task sent to queue")
    
    # Wait for result
    try:
        task_result = result.get(timeout=10)
        print(f"Task result: {task_result}")
    except Exception as e:
        print(f"Error getting result: {e}")