import redis
import json

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, db=0)

# Test Redis connection
print("Redis ping:", r.ping())

# Check if celery queue exists
queue_length = r.llen('celery')
print("Celery queue length:", queue_length)

# Add a simple task to the queue
task_data = {
    'id': 'test-task-id',
    'task': 'src.tasks.video_tasks.generate_assembler_video_task',
    'args': [1, 'Test prompt'],
    'kwargs': {}
}

r.lpush('celery', json.dumps(task_data))
print("Added task to queue")

# Check queue length again
queue_length = r.llen('celery')
print("Celery queue length after adding task:", queue_length)