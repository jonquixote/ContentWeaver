import os
import sys
import time

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'money_weaver_backend'))

from money_weaver_backend.src.services.video.tts_service import tts_service
from money_weaver_backend.src.services.video.stock_footage_service import stock_service
from money_weaver_backend.src.services.video.assembly_service import assembly_service

def test_complete_assembler_pipeline_offline():
    \"\"\"Test the complete assembler pipeline without relying on external APIs\"\"\"
    print(\"Testing Complete Assembler Pipeline (Offline Mode)...\")
    
    # Test 1: TTS generation
    print(\"\\n1. Testing TTS generation...\")
    script = \"Welcome to MoneyWeaver! This is a demonstration of our video assembler pipeline. We're creating a test video using sample footage and text-to-speech technology.\"
    audio_file = tts_service.generate_script_tts(script, \"en\")
    if audio_file and os.path.exists(audio_file):
        print(f\"TTS generated successfully: {audio_file}\")
    else:
        print(\"Failed to generate TTS\")
        return
    
    # Test 2: Stock footage search (using sample videos)
    print(\"\\n2. Testing stock footage search...\")
    # This will use sample videos since we don't have API keys configured
    video_files = stock_service.get_stock_videos_for_script(script, max_videos=2)
    if video_files and len(video_files) >= 2:
        print(f\"Found {len(video_files)} sample videos:\")
        for video in video_files:
            print(f\"  - {video}\")
    else:
        print(\"Failed to get sample videos\")
        return
    
    # Test 3: Video assembly
    print(\"\\n3. Testing video assembly...\")
    output_file = assembly_service.assemble_video(
        video_files=video_files[:2],  # Use first 2 videos
        audio_file=audio_file,
        output_filename=\"complete_test_assembly.mp4\",
        duration=15
    )
    
    if output_file and os.path.exists(output_file):
        print(f\"Video assembled successfully: {output_file}\")
        print(\"\\n✅ Complete assembler pipeline test completed successfully!\")
    else:
        print(\"Failed to assemble video\")
        return

if __name__ == \"__main__\":
    test_complete_assembler_pipeline_offline()