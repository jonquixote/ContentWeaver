import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:5004/api"

def test_video_generation_fix():
    """Test video generation with the updated assembly service"""
    print("Testing Video Generation with Updated Assembly Service...")
    
    # Create a new project for testing
    print("\n1. Creating a new test project...")
    project_data = {
        "title": "Test Project - Assembly Fix",
        "description": "Testing the updated assembly service",
        "user_id": 1,  # Default user
        "workflow_type": "assembler"
    }
    
    try:
        create_response = requests.post(f"{BASE_URL}/projects", json=project_data)
        if create_response.status_code == 201:
            project = create_response.json()
            project_id = project['id']
            print(f"Created test project with ID: {project_id}")
        else:
            print(f"Failed to create project: {create_response.text}")
            return
    except Exception as e:
        print(f"Error creating project: {e}")
        return
    
    # Generate assembler video
    print("\n2. Starting video generation...")
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
    print("\n3. Monitoring task status (60 attempts, 5-second intervals)...")
    max_attempts = 60
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
    
    # Show final project status
    print("\n4. Checking final project status...")
    try:
        response = requests.get(f"{BASE_URL}/projects/{project_id}")
        if response.status_code == 200:
            project = response.json()
            print(f"Final project status: {project.get('status', 'Unknown')}")
            if project.get('video_url'):
                print(f"Final video URL: {project['video_url']}")
                # Check if file exists
                import os
                final_path = f"/Users/johnny/Downloads/MoneyWeaver/money_weaver_backend/final/project_{project_id}_assembler.mp4"
                if os.path.exists(final_path):
                    file_size = os.path.getsize(final_path)
                    print(f"✅ Video file exists! Size: {file_size} bytes")
                else:
                    print("❌ Video file does not exist!")
            else:
                print("No video URL in project")
        else:
            print(f"Failed to get project status: {response.text}")
    except Exception as e:
        print(f"Error getting project status: {e}")

if __name__ == "__main__":
    test_video_generation_fix()