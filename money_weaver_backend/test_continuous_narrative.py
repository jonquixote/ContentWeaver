import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.services.llm_service import llm_service
from src.services.script_parsing_service import script_parsing_service
from src.services.video.video_settings import VideoSettings
from src.services.video.tts_service import tts_service
import time

def test_continuous_narrative():
    """Test our improved continuous narrative generation"""
    print("Testing continuous narrative generation...")
    
    # Test with a 30-second video
    video_settings = VideoSettings(duration=30)
    print(f"Video settings: {video_settings.to_dict()}")
    
    # Test prompt about ecology discoveries (the example from the issue)
    prompt = "Ecology's Groundbreaking Discoveries in 2025"
    print(f"Test prompt: {prompt}")
    
    # Generate script
    script = llm_service.generate_script(prompt, 1, "groq/llama-3.3-70b-versatile", 30)
    print(f"Generated script:\n{script}")
    
    # Parse script
    parsed_script = script_parsing_service.parse_script(script)
    print(f"Parsed script title: {parsed_script.get('title')}")
    print(f"Full narrative: {parsed_script.get('full_narrative', '')}")
    
    # Extract voiceover text
    voiceover_text = script_parsing_service.extract_voiceover_text(parsed_script)
    print(f"Voiceover text: {voiceover_text}")
    
    # Check if the voiceover is a continuous narrative
    # Count sentences to see if it flows properly
    import re
    sentences = re.split(r'[.!?]+', voiceover_text)
    sentences = [s.strip() for s in sentences if s.strip()]
    print(f"Number of sentences: {len(sentences)}")
    
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
        
    # Check if scenes have continuous narrative flow
    scenes = parsed_script.get('scenes', [])
    if scenes:
        print("\nScene voiceovers:")
        for i, scene in enumerate(scenes):
            voiceover = scene.get('voiceover', '')
            print(f"Scene {i+1}: {voiceover}")
            
            # Check if this voiceover is part of the full narrative
            if voiceover in parsed_script.get('full_narrative', ''):
                print(f"  ✓ Scene {i+1} voiceover is part of the full narrative")
            else:
                print(f"  ✗ Scene {i+1} voiceover may not be part of the full narrative")
    
    print("\nTest completed!")

if __name__ == '__main__':
    test_continuous_narrative()