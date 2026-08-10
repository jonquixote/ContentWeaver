import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:5004/api"

def test_existing_project_video_generation():
    """Test video generation with an existing project"""
    print("Testing Video Generation with Existing Project...")
    
    # First, let's get existing projects
    print("\n1. Getting existing projects...")
    try:
        response = requests.get(f"{BASE_URL}/projects")
        if response.status_code == 200:
            projects = response.json()
            if projects:
                project_id = projects[0]['id']
                print(f"Using existing project with ID: {project_id}")
            else:
                print("No existing projects found. Creating a test project...")
                # Create a simple project for testing
                project_data = {
                    "title": "Test Video Project",
                    "description": "A test project for video generation",
                    "user_id": 1,  # Default user
                    "workflow_type": "assembler"
                }
                create_response = requests.post(f"{BASE_URL}/projects", json=project_data)
                if create_response.status_code == 201:
                    project = create_response.json()
                    project_id = project['id']
                    print(f"Created test project with ID: {project_id}")
                else:
                    print(f"Failed to create project: {create_response.text}")
                    return
        else:
            print(f"Failed to get projects: {response.text}")
            return
    except Exception as e:
        print(f"Error getting/creating project: {e}")
        return
    
    # Generate assembler video
    print("\n2. Starting video generation...")
    video_data = {
        "project_id": project_id,
        "prompt": "Create a short educational video about the benefits of artificial intelligence in modern business operations. Include examples of AI in customer service, data analysis, and automation."
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
    print("\n3. Monitoring task status (30 attempts, 5-second intervals)...")
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
    
    # Show final project status
    print("\n4. Checking final project status...")
    try:
        response = requests.get(f"{BASE_URL}/projects/{project_id}")
        if response.status_code == 200:
            project = response.json()
            print(f"Final project status: {project.get('status', 'Unknown')}")
            if project.get('video_url'):
                print(f"Final video URL: {project['video_url']}")
        else:
            print(f"Failed to get project status: {response.text}")
    except Exception as e:
        print(f"Error getting project status: {e}")

if __name__ == "__main__":
    test_existing_project_video_generation()