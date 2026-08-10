#!/usr/bin/env python3
"""
Test script to explore available Kokoro voices
"""
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_kokoro_voices():
    """Test Kokoro voices"""
    try:
        print("Testing Kokoro voices...")
        from kokoro import KPipeline
        import torch
        
        print("Kokoro successfully imported")
        
        # Initialize the model
        print("Initializing Kokoro model...")
        pipeline = KPipeline(lang_code='a')  # American English
        print("Kokoro model initialized successfully")
        
        # Try to get available voices
        print("Checking available voices...")
        
        # Based on Kokoro documentation, these are common voice options:
        voices = [
            'af_heart',      # Female voice
            'af_sky',        # Female voice
            'af_queen',      # Female voice
            'am_regular',    # Male voice
            'am_narrative',  # Male voice
            'am_news',       # Male voice
            'am_excited',    # Male voice
            'am_soft',       # Male voice
            'am_breathy',    # Male voice
            'am_bright',     # Male voice
            'am_warlock',    # Male voice
            'am_melancholic', # Male voice
            'am_shouty',     # Male voice
            'am_fried',      # Male voice
            'am_grumpy',     # Male voice
            'am_happy',      # Male voice
            'am_fearful',    # Male voice
            'am_gentle',     # Male voice
            'am_bold',       # Male voice
            'am_husky',      # Male voice
            'am_laughter',   # Male voice
            'am_whisper',    # Male voice
            'am_default',    # Default male voice
        ]
        
        # Test text
        test_text = "This is a test of different voice options in Kokoro."
        
        # Test a few voices to see which ones work
        working_voices = []
        for voice in voices:
            try:
                print(f"Testing voice: {voice}")
                generator = pipeline(test_text, voice=voice)
                # Try to get the first segment
                for i, (gs, ps, audio) in enumerate(generator):
                    print(f"  ✓ Voice {voice} works")
                    working_voices.append(voice)
                    break
            except Exception as e:
                print(f"  ✗ Voice {voice} failed: {e}")
        
        print(f"\nWorking voices: {working_voices}")
        return working_voices
        
    except Exception as e:
        print(f"Error testing Kokoro voices: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    voices = test_kokoro_voices()
    print(f"\nFound {len(voices)} working voices:")
    for voice in voices:
        print(f"  - {voice}")