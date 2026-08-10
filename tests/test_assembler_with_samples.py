import os
import sys
import time

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'money_weaver_backend'))

from money_weaver_backend.src.services.video.tts_service import tts_service
from money_weaver_backend.src.services.video.assembly_service import assembly_service

def test_assembler_with_samples():
    """Test the assembler pipeline with sample videos"""
    print("Testing Assembler Pipeline with Sample Videos...")
    
    # Test 1: TTS generation
    print("\n1. Testing TTS generation...")
    script = "Welcome to MoneyWeaver! This is a demonstration of our video assembler pipeline. We're creating a test video using sample footage and text-to-speech technology."
    audio_file = tts_service.generate_script_tts(script, "en")
    if audio_file and os.path.exists(audio_file):
        print(f"TTS generated successfully: {audio_file}")
    else:
        print("Failed to generate TTS")
        return
    
    # Test 2: Video assembly with sample videos
    print("\n2. Testing video assembly with sample videos...")
    # Use our sample videos
    work_dir = os.path.join(os.path.dirname(__file__), 'money_weaver_backend', 'src', 'work')
    sample_videos = [
        os.path.join(work_dir, 'sample1.mp4'),
        os.path.join(work_dir, 'sample2.mp4')
    ]
    
    # Check if sample videos exist
    valid_videos = [v for v in sample_videos if os.path.exists(v)]
    if len(valid_videos) < 2:
        print("Need at least 2 sample videos for testing")
        return
    
    print(f"Using {len(valid_videos)} sample videos:")
    for video in valid_videos:
        print(f"  - {video}")
    
    # Assemble video
    output_file = assembly_service.assemble_video(
        video_files=valid_videos,
        audio_file=audio_file,
        output_filename="test_assembly_with_samples.mp4",
        duration=10
    )
    
    if output_file and os.path.exists(output_file):
        print(f"Video assembled successfully: {output_file}")
        print("\n✅ Assembler pipeline test completed successfully!")
    else:
        print("Failed to assemble video")
        return

if __name__ == "__main__":
    test_assembler_with_samples()