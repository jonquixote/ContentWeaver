import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.services.llm_service import llm_service
from src.services.script_parsing_service import script_parsing_service
from src.services.video.video_settings import VideoSettings
from src.services.video.tts_service import tts_service
import time

def test_improved_video_assembler():
    """Test our improved video assembler pipeline"""
    print("Testing improved video assembler pipeline...")
    
    # Test with a 30-second video
    video_settings = VideoSettings(duration=30)
    print(f"Video settings: {video_settings.to_dict()}")
    
    # Test prompt about biology discoveries
    prompt = "Breakthroughs in Biology 2024"
    print(f"Test prompt: {prompt}")
    
    # Generate script
    script = llm_service.generate_script(prompt, 1, "groq/llama-3.3-70b-versatile", 30)
    print(f"Generated script:\n{script}")
    
    # Parse script
    parsed_script = script_parsing_service.parse_script(script)
    print(f"Parsed script title: {parsed_script.get('title')}")
    
    # Extract voiceover text
    voiceover_text = script_parsing_service.extract_voiceover_text(parsed_script)
    print(f"Voiceover text: {voiceover_text}")
    
    # Count words in voiceover
    word_count = len(voiceover_text.split())
    print(f"Word count: {word_count}")
    
    # Expected word count for 30 seconds at 2.5 words/second
    expected_words = int(30 * 2.5)
    print(f"Expected words (150 WPM): {expected_words}")
    
    # Check if we're in the right range
    if word_count >= expected_words * 0.8 and word_count <= expected_words * 1.2:
        print("✓ Word count is within expected range for 150 WPM")
    else:
        print("✗ Word count is outside expected range")
        
    # Check scene count
    scene_count = len(parsed_script.get('scenes', []))
    expected_scenes = video_settings.get_scene_count()
    print(f"Scene count: {scene_count}")
    print(f"Expected scenes: {expected_scenes}")
    
    if scene_count >= expected_scenes * 0.8 and scene_count <= expected_scenes * 1.2:
        print("✓ Scene count is within expected range")
    else:
        print("✗ Scene count is outside expected range")
        
    # Calculate average clip duration
    if scene_count > 0:
        avg_clip_duration = 30.0 / scene_count
        print(f"Average clip duration: {avg_clip_duration:.2f} seconds")
        
        if avg_clip_duration >= 3.0 and avg_clip_duration <= 4.0:
            print("✓ Average clip duration is within target range (3-4 seconds)")
        else:
            print("✗ Average clip duration is outside target range")
    
    # Test TTS generation
    print("\nGenerating TTS...")
    tts_file = tts_service.generate_tts(voiceover_text)
    if tts_file and os.path.exists(tts_file):
        print(f"✓ TTS generated successfully: {tts_file}")
        
        # Get file size
        file_size = os.path.getsize(tts_file)
        print(f"TTS file size: {file_size} bytes")
        
        # Clean up TTS file
        os.remove(tts_file)
    else:
        print("✗ Failed to generate TTS")
        
    print("\nTest completed!")

if __name__ == '__main__':
    test_improved_video_assembler()