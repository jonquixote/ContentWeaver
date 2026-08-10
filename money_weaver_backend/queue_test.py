import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.tasks.video_tasks import generate_assembler_video_task

if __name__ == '__main__':
    # Send task directly with explicit queue
    result = generate_assembler_video_task.apply_async(args=[1, "Test prompt"], queue='celery')
    print(f"Task ID: {result.id}")
    print("Task sent to queue")
    
    # Check task status
    print("Task state:", result.state)