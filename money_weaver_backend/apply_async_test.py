import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import the same way as the Flask backend
from src.tasks.video_tasks import generate_assembler_video_task

if __name__ == '__main__':
    # Send task using apply_async method
    print("Sending task using apply_async() method...")
    celery_task = generate_assembler_video_task.apply_async(args=[1, "Test prompt from apply_async test"])
    print(f"Task ID: {celery_task.id}")
    print("Task sent to queue using apply_async() method")
    
    # Check task status
    print("Task state:", celery_task.state)