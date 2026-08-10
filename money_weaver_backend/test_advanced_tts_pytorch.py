#!/usr/bin/env python3
"""
Test script for the advanced TTS service with PyTorch
"""
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Test PyTorch availability
try:
    import torch
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    PYTORCH_AVAILABLE = True
except ImportError:
    print("PyTorch not available")
    PYTORCH_AVAILABLE = False

from services.video.advanced_tts_service import advanced_tts_service

def test_advanced_tts():
    """Test the advanced TTS service"""
    print("Testing Advanced TTS Service...")
    
    # Test text
    test_text = "This is a test of the advanced text to speech service in MoneyWeaver."
    
    # Test with fallback to gTTS
    print("Testing with gTTS fallback...")
    result = advanced_tts_service.generate_tts(test_text, model_type="kokoro")
    
    if result:
        print(f"Success! Audio file generated at: {result}")
    else:
        print("Failed to generate audio file")
        
    return result is not None

if __name__ == "__main__":
    print(f"Python version: {sys.version}")
    print(f"PyTorch available: {PYTORCH_AVAILABLE}")
    print()
    
    success = test_advanced_tts()
    if success:
        print("\nAdvanced TTS service test completed successfully!")
    else:
        print("\nAdvanced TTS service test failed!")
        sys.exit(1)