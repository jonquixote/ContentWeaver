import sys
import os
sys.path.append('/Users/johnny/Downloads/MoneyWeaver/money_weaver_backend/src')

# Set up the environment
os.environ['FLASK_APP'] = 'main.py'

from services.video.stock_footage_service import stock_service
from services.video.tts_service import tts_service
from services.video.assembly_service import assembly_service

def test_assembler_pipeline():
    """Test the complete assembler pipeline"""
    print("Testing Assembler Video Pipeline...")
    
    # Test 1: Stock footage search
    print("\n1. Testing stock footage search...")
    script = "Create a video about AI technology and its impact on business"
    videos = stock_service.get_stock_videos_for_script(script, max_videos=3)
    print(f"Found {len(videos)} stock videos")
    for video_path, duration, metadata in videos:
        print(f"  - Path: {video_path}")
        print(f"    Duration: {duration}")
        print(f"    Metadata: {metadata}")
    
    # Test 2: TTS generation
    print("\n2. Testing TTS generation...")
    audio_file = tts_service.generate_script_tts("This is a test of the text to speech system. Artificial intelligence is revolutionizing how we work and live.", "en")
    print(f"TTS generated: {audio_file}")
    
    # Test 3: Video assembly (if we have videos)
    if videos and audio_file:
        print("\n3. Testing video assembly...")
        # Create simple scene timings for testing
        scene_timings = [
            {"duration": 7.5, "content": "Introduction to AI"},
            {"duration": 7.5, "content": "AI impact on business"}
        ]
        output_file = assembly_service.assemble_video(
            video_files=videos[:2],  # Use first 2 videos
            audio_file=audio_file,
            scene_timings=scene_timings,
            output_filename="test_assembly.mp4",
            total_duration=15
        )
        print(f"Video assembled: {output_file}")
    else:
        print("\n3. Skipping video assembly (no videos or audio available)")
    
    print("\nPipeline test completed!")

if __name__ == "__main__":
    test_assembler_pipeline()