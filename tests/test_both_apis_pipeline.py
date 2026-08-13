import os
import sys

# Add the backend directory to the path
sys.path.insert(0, 'money_weaver_backend')

from src.services.video.tts_service import tts_service
from src.services.video.stock_footage_service import stock_service
from src.services.video.assembly_service import assembly_service

def test_complete_pipeline_with_both_apis():
    """Test the complete assembler pipeline with both Pexels and Pixabay API keys"""
    print("Testing Complete Assembler Pipeline with Both Pexels and Pixabay APIs...")
    
    # Set both API keys (from environment; never commit live keys)
    stock_service.pexels_api_key = os.getenv('PEXELS_API_KEY')
    stock_service.pixabay_api_key = os.getenv('PIXABAY_API_KEY')
    stock_service.use_sample_videos = False
    
    print("\n1. Generating TTS...")
    script = "Welcome to MoneyWeaver! This is a demonstration of our video assembler pipeline using real stock footage from both Pexels and Pixabay APIs."
    audio_file = tts_service.generate_script_tts(script, "en")
    if not (audio_file and os.path.exists(audio_file)):
        print("❌ Failed to generate TTS")
        return False
    print(f"✅ TTS generated: {audio_file}")
    
    print("\n2. Searching for stock footage from both services...")
    # Get stock videos based on the script
    video_files = stock_service.get_stock_videos_for_script(script, max_videos=4)
    if not (video_files and len(video_files) >= 1):
        print("❌ Failed to get stock footage")
        return False
    print(f"✅ Found {len(video_files)} stock videos:")
    for i, video in enumerate(video_files):
        print(f"   {i+1}. {os.path.basename(video)}")
    
    print("\n3. Assembling final video...")
    output_file = assembly_service.assemble_video(
        video_files=video_files,
        audio_file=audio_file,
        output_filename="both_apis_test_assembly.mp4",
        duration=25
    )
    
    if not (output_file and os.path.exists(output_file)):
        print("❌ Failed to assemble video")
        return False
    
    print(f"✅ Video assembled successfully: {output_file}")
    print("\n🎉 Complete assembler pipeline with both APIs test completed successfully!")
    return True

if __name__ == "__main__":
    success = test_complete_pipeline_with_both_apis()
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)