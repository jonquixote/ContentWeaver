import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:5004/api"

def test_simple_video_generation():
    print("Testing Simple Video Generation...")
    
    # Use existing user (ID 1)
    user_id = 1
    
    # Create a project
    print("\n1. Creating project...")
    project_data = {
        "title": "Simple Test Video",
        "description": "A simple test video",
        "user_id": user_id,
        "workflow_type": "assembler"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/projects", json=project_data)
        if response.status_code == 201:
            project = response.json()
            project_id = project['id']
            print(f"Project created with ID: {project_id}")
        else:
            print(f"Failed to create project: {response.text}")
            return
    except Exception as e:
        print(f"Error creating project: {e}")
        return
    
    # Generate assembler video with a simple prompt
    print("\n2. Starting simple video generation...")
    video_data = {
        "project_id": project_id,
        "prompt": "Create a short video about technology"
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
    
    # Monitor task status for a short time
    print("\n3. Monitoring task status (10 attempts)...")
    for attempt in range(10):
        try:
            response = requests.get(f"{BASE_URL}/task-status/{celery_task_id}")
            if response.status_code == 200:
                status = response.json()
                print(f"  Attempt {attempt + 1}: Status: {status['state']} - {status['status']}")
                
                if status['state'] == 'SUCCESS':
                    print("✅ Video generation completed successfully!")
                    if 'result' in status and 'video_url' in status['result']:
                        print(f"Video available at: {status['result']['video_url']}")
                    break
                elif status['state'] == 'FAILURE':
                    print(f"❌ Video generation failed: {status['status']}")
                    break
            else:
                print(f"Failed to get task status: {response.text}")
        except Exception as e:
            print(f"Error getting task status: {e}")
        
        time.sleep(5)  # Wait 5 seconds between checks
    
    print("\nTest monitoring completed!")

if __name__ == "__main__":
    test_simple_video_generation()