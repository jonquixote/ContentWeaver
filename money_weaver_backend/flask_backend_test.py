import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.tasks.video_tasks import generate_assembler_video_task

if __name__ == '__main__':
    # Send task using the same method as the Flask backend
    result = generate_assembler_video_task.delay(1, "Test prompt from Flask backend")
    print(f"Task ID: {result.id}")
    print("Task sent to queue using delay() method")
    
    # Check task status
    print("Task state:", result.state)