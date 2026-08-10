import sys
import os
import json
import redis
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

if __name__ == '__main__':
    # Connect to Redis directly
    r = redis.Redis(host='localhost', port=6379, db=0)
    
    # Create a task message
    task_message = {
        'task': 'src.tasks.video_tasks.generate_assembler_video_task',
        'id': 'test-task-001',
        'args': [1, 'Test prompt'],
        'kwargs': {},
        'retries': 0,
        'eta': None,
        'expires': None,
        'utc': True,
        'callbacks': None,
        'errbacks': None,
        'timelimit': [None, None],
        'taskset': None,
        'chord': None,
    }
    
    # Serialize the task message
    task_message_json = json.dumps(task_message, separators=(',', ':'))
    
    # Add the task to the Redis queue
    r.lpush('celery', task_message_json)
    
    print("Task added to Redis queue directly")
    print("Queue length:", r.llen('celery'))