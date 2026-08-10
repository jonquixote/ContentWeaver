import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.services.video.video_settings import VideoSettings

def test_video_settings():
    """Test our video settings calculations"""
    print("Testing video settings...")
    
    # Test different durations
    test_durations = [15, 30, 60, 120]
    
    for duration in test_durations:
        print(f"\n--- Testing {duration}-second video ---")
        settings = VideoSettings(duration=duration)
        
        scene_count = settings.get_scene_count()
        words_per_scene = settings.get_words_per_scene()
        total_words = words_per_scene * scene_count
        
        print(f"Scene count: {scene_count}")
        print(f"Words per scene: {words_per_scene}")
        print(f"Total words: {total_words}")
        print(f"Target words (2.5 words/sec): {int(duration * 2.5)}")
        
        # Check if we're in the right range
        expected_clips = duration // 3  # 1 clip per 3 seconds
        print(f"Expected clips (1 per 3 sec): {expected_clips}")
        
        if scene_count >= expected_clips * 0.8 and scene_count <= expected_clips * 1.2:
            print("✓ Scene count is within expected range")
        else:
            print("✗ Scene count is outside expected range")

if __name__ == '__main__':
    test_video_settings()