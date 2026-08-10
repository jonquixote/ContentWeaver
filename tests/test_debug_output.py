import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:5004/api"

def test_debug_video_generation():
    """Test video generation with debug output"""
    print("Testing Video Generation with Debug Output...")
    
    # Use existing project 21
    project_id = 21
    
    # Generate assembler video
    print("\n1. Starting video generation...")
    video_data = {
        "project_id": project_id,
        "prompt": "Create a 30-second video about cool beans. Include scenes of different types of beans, their uses in cooking, and nutritional benefits."
    }
    
    try:
        response = requests.post(f"{BASE_URL}/generate/assembler", json=video_data)
        if response.status_code == 202:
            result = response.json()
            celery_task_id = result['celery_task_id']
            print(f"Video generation started with task ID: {celery_task_id}")
        else:
            print(f"Failed to start video generation: {response.text}")
            return
    except Exception as e:
        print(f"Error starting video generation: {e}")
        return
    
    # Monitor task status for a reasonable amount of time
    print("\n2. Monitoring task status (30 attempts, 5-second intervals)...")
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{BASE_URL}/task-status/{celery_task_id}")
            if response.status_code == 200:
                status = response.json()
                print(f"  Attempt {attempt + 1:2d}: State: {status['state']:12s} - Progress: {status.get('current', 0):3d}% - {status.get('status', 'Unknown')}")
                
                if status['state'] == 'SUCCESS':
                    print("✅ Video generation completed successfully!")
                    if 'result' in status and 'result' in status['result']:
                        print(f"Video available at: {status['result']['result'].get('video_url', 'Unknown')}")
                    break
                elif status['state'] == 'FAILURE':
                    print(f"❌ Video generation failed: {status.get('status', 'Unknown error')}")
                    break
                elif status['state'] == 'ERROR':
                    print(f"❌ Error retrieving task status: {status.get('status', 'Unknown error')}")
                    break
            else:
                print(f"Failed to get task status: {response.text}")
        except Exception as e:
            print(f"Error getting task status: {e}")
        
        time.sleep(5)  # Wait 5 seconds between checks
    
    print("\nTest monitoring completed!")

if __name__ == "__main__":
    test_debug_video_generation()