#!/usr/bin/env python3
"""
Test script for the advanced TTS service with Kokoro
"""
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Test if Kokoro is available
try:
    from kokoro import KPipeline
    print("Kokoro successfully imported")
    KOKORO_AVAILABLE = True
except ImportError:
    print("Kokoro not available")
    KOKORO_AVAILABLE = False

# Import our service
try:
    from services.video.advanced_tts_service import advanced_tts_service
    print("Advanced TTS service successfully imported")
except Exception as e:
    print(f"Error importing advanced TTS service: {e}")
    sys.exit(1)

def test_advanced_tts():
    """Test the advanced TTS service"""
    print("Testing Advanced TTS Service...")
    
    # Test text
    test_text = "This is a test of the advanced text to speech service in MoneyWeaver."
    
    # Test with Kokoro if available, otherwise fallback to gTTS
    print("Testing with Kokoro if available...")
    result = advanced_tts_service.generate_tts(test_text, model_type="kokoro")
    
    if result:
        print(f"Success! Audio file generated at: {result}")
    else:
        print("Failed to generate audio file")
        
    return result is not None

if __name__ == "__main__":
    print(f"Python version: {sys.version}")
    print(f"Kokoro available: {KOKORO_AVAILABLE}")
    print()
    
    success = test_advanced_tts()
    if success:
        print("\nAdvanced TTS service test completed successfully!")
    else:
        print("\nAdvanced TTS service test failed!")
        sys.exit(1)