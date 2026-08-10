import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:5004/api"

def test_video_generation():
    print("Testing Video Generation Pipeline...")
    
    # First get existing users or create one properly
    print("\n1. Getting/creating user...")
    try:
        # Try to get existing users
        response = requests.get(f"{BASE_URL}/users")
        if response.status_code == 200:
            users = response.json()
            if users:
                user_id = users[0]['id']
                print(f"Using existing user with ID: {user_id}")
            else:
                # Create a new user with proper password
                user_data = {
                    "username": "test_user",
                    "email": "test@example.com",
                    "password": "testpassword123"
                }
                response = requests.post(f"{BASE_URL}/auth/register", json=user_data)
                if response.status_code == 201:
                    user = response.json()
                    user_id = user['id']
                    print(f"User created with ID: {user_id}")
                else:
                    print(f"Failed to create user: {response.text}")
                    return
        else:
            print(f"Failed to get users: {response.text}")
            return
    except Exception as e:
        print(f"Error getting/creating user: {e}")
        return
    
    # Create a project
    print("\n2. Creating project...")
    project_data = {
        "title": "Test AI Video",
        "description": "A test video about AI technology",
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
    
    # Generate assembler video
    print("\n3. Starting video generation...")
    video_data = {
        "project_id": project_id,
        "prompt": "Create a short video about the impact of artificial intelligence on modern business operations. Include examples of AI in customer service, data analysis, and automation."
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
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{BASE_URL}/task-status/{celery_task_id}")
            if response.status_code == 200:
                status = response.json()
                print(f"  Status: {status['state']} - {status['status']}")
                
                if status['state'] == 'SUCCESS':
                    print("Video generation completed successfully!")
                    if 'result' in status and 'video_url' in status['result']:
                        print(f"Video available at: {status['result']['video_url']}")
                    break
                elif status['state'] == 'FAILURE':
                    print(f"Video generation failed: {status['status']}")
                    break
            else:
                print(f"Failed to get task status: {response.text}")
        except Exception as e:
            print(f"Error getting task status: {e}")
        
        time.sleep(10)  # Wait 10 seconds between checks
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_video_generation()