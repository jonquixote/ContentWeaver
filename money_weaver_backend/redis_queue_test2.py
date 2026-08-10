import sys
import os
import json
import redis
import uuid
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

if __name__ == '__main__':
    # Connect to Redis directly
    r = redis.Redis(host='localhost', port=6379, db=0)
    
    # Create a task ID
    task_id = str(uuid.uuid4())
    
    # Create the task body (args, kwargs, properties)
    task_body = [
        [1, 'Test prompt'],  # args
        {},  # kwargs
        {
            'callbacks': None,
            'errbacks': None,
            'chain': None,
            'chord': None,
        }
    ]
    
    # Create the task headers
    task_headers = {
        'lang': 'py',
        'task': 'src.tasks.video_tasks.generate_assembler_video_task',
        'id': task_id,
        'root_id': task_id,
        'parent_id': None,
        'argsrepr': "(1, 'Test prompt')",
        'kwargsrepr': '{}',
        'origin': f'gen{os.getpid()}@{os.uname().nodename}',
    }
    
    # Create the message
    message = {
        'body': json.dumps(task_body, separators=(',', ':')),
        'headers': task_headers,
        'content-type': 'application/json',
        'content-encoding': 'utf-8',
        'properties': {
            'correlation_id': task_id,
            'reply_to': '',
        }
    }
    
    # Serialize the entire message
    message_json = json.dumps(message, separators=(',', ':'))
    
    # Add the task to the Redis queue
    r.lpush('celery', message_json)
    
    print(f"Task {task_id} added to Redis queue directly")
    print("Queue length:", r.llen('celery'))