import os
import sys
import time
import requests

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'money_weaver_backend'))

# Configuration
BASE_URL = "http://localhost:5004/api"

def test_complete_assembler_pipeline():
    """Test the complete assembler pipeline with a real Celery task"""
    print("Testing Complete Assembler Pipeline...")
    
    # First, let's make sure we have a user
    print("\n1. Checking for existing users...")
    try:
        response = requests.get(f"{BASE_URL}/users")
        if response.status_code == 200:
            users = response.json()
            if users:
                user_id = users[0]['id']
                print(f"Using existing user with ID: {user_id}")
            else:
                print("No users found")
                return
        else:
            print(f"Failed to get users: {response.text}")
            return
    except Exception as e:
        print(f"Error getting users: {e}")
        return
    
    # Create a project
    print("\n2. Creating project...")
    project_data = {
        "title": "Test Assembler Pipeline",
        "description": "A test of the complete assembler pipeline",
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
    print("\n3. Starting assembler video generation...")
    video_data = {
        "project_id": project_id,
        "prompt": "Create a short video about technology and innovation"
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
    
    # Monitor task status
    print("\n4. Monitoring task status...")
    max_attempts = 30  # Wait up to 5 minutes (10 seconds * 30)
    for attempt in range(max_attempts):
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
                elif status['state'] == 'PROGRESS':
                    # Continue monitoring
                    pass
            else:
                print(f"Failed to get task status: {response.text}")
        except Exception as e:
            print(f"Error getting task status: {e}")
        
        # Wait before checking again
        time.sleep(10)
    else:
        print("⚠️  Video generation timed out. Task may still be running.")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_complete_assembler_pipeline()