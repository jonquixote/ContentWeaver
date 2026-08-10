#!/usr/bin/env python3
"""
Test script to explore Kokoro voice customization options
"""
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_kokoro_customization():
    """Test Kokoro voice customization options"""
    try:
        print("Testing Kokoro voice customization options...")
        from kokoro import KPipeline
        import torch
        import torchaudio
        
        print("Kokoro successfully imported")
        
        # Initialize the model
        print("Initializing Kokoro model...")
        pipeline = KPipeline(lang_code='a')  # American English
        print("Kokoro model initialized successfully")
        
        # Test text
        test_text = "Hello, this is a test of voice customization options."
        
        # Test with different parameters that might affect voice characteristics
        print("\nTesting voice customization parameters...")
        
        # Test af_heart with different parameters
        print("Testing af_heart with speed parameter...")
        try:
            generator = pipeline(test_text, voice='af_heart', speed=0.8)  # Slower speed
            for i, (gs, ps, audio) in enumerate(generator):
                print("  ✓ af_heart with speed=0.8 works")
                break
        except Exception as e:
            print(f"  ✗ af_heart with speed=0.8 failed: {str(e)[:50]}...")
        
        print("Testing af_heart with different speed...")
        try:
            generator = pipeline(test_text, voice='af_heart', speed=1.2)  # Faster speed
            for i, (gs, ps, audio) in enumerate(generator):
                print("  ✓ af_heart with speed=1.2 works")
                break
        except Exception as e:
            print(f"  ✗ af_heart with speed=1.2 failed: {str(e)[:50]}...")
        
        # Test af_sky with different parameters
        print("Testing af_sky with speed parameter...")
        try:
            generator = pipeline(test_text, voice='af_sky', speed=0.9)
            for i, (gs, ps, audio) in enumerate(generator):
                print("  ✓ af_sky with speed=0.9 works")
                break
        except Exception as e:
            print(f"  ✗ af_sky with speed=0.9 failed: {str(e)[:50]}...")
        
        # Check if we can access the model directly for voice manipulation
        print("\nChecking if we can access model for voice manipulation...")
        try:
            # Try to access the model's voice conversion capabilities
            # This is experimental and might not work
            print("Attempting to access voice conversion features...")
            # This would be implementation-specific and depends on Kokoro's API
            
        except Exception as e:
            print(f"  Voice conversion features not directly accessible: {str(e)[:50]}...")
        
        print("\nVoice customization test completed.")
        
    except Exception as e:
        print(f"Error testing Kokoro voice customization: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_kokoro_customization()