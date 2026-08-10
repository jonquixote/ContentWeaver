import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.tasks.video_tasks import generate_assembler_video_task
from src.services.video.video_settings import VideoSettings

def test_video_assembler():
    """Test the video assembler with our fixes"""
    print("Testing video assembler with fixes...")
    
    # Test with a 30-second video
    video_settings = VideoSettings(duration=30)
    print(f"Video settings: {video_settings.to_dict()}")
    
    # Test prompt about biology discoveries
    prompt = "Breakthroughs in Biology 2024"
    print(f"Test prompt: {prompt}")
    
    # Send task directly
    result = generate_assembler_video_task.delay(1, prompt, 30)
    print(f"Task ID: {result.id}")
    print("Task sent to queue")
    
    # Poll for task completion
    while not result.ready():
        print("Task is still running...")
        time.sleep(5)
        
        # Get task status
        task_state = result.state
        print(f"Task state: {task_state}")
        
        if task_state == 'PROGRESS':
            try:
                meta = result.info
                if isinstance(meta, dict):
                    current = meta.get('current', 0)
                    total = meta.get('total', 100)
                    status = meta.get('status', 'Unknown')
                    print(f"Progress: {current}/{total} - {status}")
            except Exception as e:
                print(f"Could not get progress info: {e}")
    
    # Task completed, get result
    print("Task completed!")
    task_result = result.get()
    print(f"Result: {task_result}")
    
    if isinstance(task_result, dict):
        if task_result.get('status') == 'Video generation completed!':
            print("SUCCESS: Video generation completed successfully!")
            print(f"Video URL: {task_result.get('result', {}).get('video_url', 'N/A')}")
            print(f"Script: {task_result.get('result', {}).get('script', 'N/A')}")
        else:
            print("ERROR: Video generation failed!")
            print(f"Error: {task_result.get('error', 'Unknown error')}")
    else:
        print("Unexpected result format")

if __name__ == '__main__':
    test_video_assembler()