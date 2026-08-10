import sys
import os
sys.path.append('/Users/johnny/Downloads/MoneyWeaver/money_weaver_backend/src')

# Set up the environment
os.environ['FLASK_APP'] = 'main.py'

from services.video.stock_footage_service import stock_service

# Test the stock footage service
print("Testing stock footage service...")
print(f"Pexels API key: {stock_service.pexels_api_key}")
print(f"Pixabay API key: {stock_service.pixabay_api_key}")
print(f"Use sample videos: {stock_service.use_sample_videos}")
print(f"Working directory: {stock_service.working_dir}")

# Test getting stock videos for a simple script
script = "Create a video about cool beans"
print(f"\nGetting stock videos for script: {script}")
videos = stock_service.get_stock_videos_for_script(script, max_videos=5)
print(f"Got {len(videos)} videos:")
for i, (video_path, duration, metadata) in enumerate(videos):
    print(f"  Video {i+1}:")
    print(f"    Path: {video_path}")
    print(f"    Duration: {duration}")
    print(f"    Metadata: {metadata}")