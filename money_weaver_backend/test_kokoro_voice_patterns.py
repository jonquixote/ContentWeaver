#!/usr/bin/env python3
"""
Test script to explore Kokoro voice naming conventions and find male voices
"""
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_kokoro_voice_patterns():
    """Test Kokoro voice patterns to find male voices"""
    try:
        print("Testing Kokoro voice patterns...")
        from kokoro import KPipeline
        import torch
        
        print("Kokoro successfully imported")
        
        # Initialize the model
        print("Initializing Kokoro model...")
        pipeline = KPipeline(lang_code='a')  # American English
        print("Kokoro model initialized successfully")
        
        # Based on the Kokoro documentation and the available voices,
        # let's try some common male voice patterns:
        # af_* = female voices
        # am_* = male voices (but they're not available in the current model)
        
        # Let's try to see if we can use custom voices or if there are other options
        print("\nTesting voice patterns...")
        
        # Test some male voice patterns that might exist
        male_voice_patterns = [
            'am_athletic', 'am_confident', 'am_deep', 'am_gruff', 'am_hero',
            'am_jovial', 'am_loud', 'am_normal', 'am_old', 'am_pro',
            'am_raspy', 'am_serious', 'am_story', 'am_strong', 'am_warm',
            'male', 'man', 'boy', 'm', 'af_male', 'am_male'
        ]
        
        working_voices = []
        
        # Test a simple text
        test_text = "Hello, this is a test of voice options."
        
        # Test the af_heart voice (known to work) for comparison
        print("Testing known working voice: af_heart")
        try:
            generator = pipeline(test_text, voice='af_heart')
            for i, (gs, ps, audio) in enumerate(generator):
                print("  ✓ af_heart works")
                working_voices.append('af_heart')
                break
        except Exception as e:
            print(f"  ✗ af_heart failed: {e}")
        
        # Test af_sky voice (known to work) for comparison
        print("Testing known working voice: af_sky")
        try:
            generator = pipeline(test_text, voice='af_sky')
            for i, (gs, ps, audio) in enumerate(generator):
                print("  ✓ af_sky works")
                working_voices.append('af_sky')
                break
        except Exception as e:
            print(f"  ✗ af_sky failed: {e}")
        
        # Test some potential male voices
        for voice in male_voice_patterns:
            try:
                print(f"Testing potential male voice: {voice}")
                generator = pipeline(test_text, voice=voice)
                for i, (gs, ps, audio) in enumerate(generator):
                    print(f"  ✓ Voice {voice} works")
                    working_voices.append(voice)
                    break
            except Exception as e:
                print(f"  ✗ Voice {voice} failed: {str(e)[:50]}...")
        
        print(f"\nWorking voices found: {working_voices}")
        return working_voices
        
    except Exception as e:
        print(f"Error testing Kokoro voice patterns: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    voices = test_kokoro_voice_patterns()
    print(f"\nSummary: Found {len(voices)} working voices:")
    for voice in voices:
        print(f"  - {voice}")