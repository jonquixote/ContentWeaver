#!/usr/bin/env python3
"""
Simple test for Kokoro TTS
"""
import os
import sys
import time

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_kokoro_directly():
    """Test Kokoro directly without our service wrapper"""
    try:
        print("Testing Kokoro directly...")
        from kokoro import KPipeline
        import soundfile as sf
        import torch
        import numpy as np
        
        print("Kokoro successfully imported")
        
        # Initialize the model
        print("Initializing Kokoro model...")
        pipeline = KPipeline(lang_code='a')  # American English
        print("Kokoro model initialized successfully")
        
        # Test text
        text = "This is a test of the Kokoro text to speech model."
        print(f"Generating audio for: {text}")
        
        # Generate audio
        generator = pipeline(text, voice='af_heart')
        
        # Get the first (and typically only) audio segment
        for i, (gs, ps, audio) in enumerate(generator):
            print(f"Generated audio segment {i}")
            print(f"Graphemes: {gs[:50]}...")
            print(f"Phonemes: {ps[:50]}...")
            print(f"Audio shape: {audio.shape}")
            print(f"Audio dtype: {audio.dtype}")
            print(f"Audio type: {type(audio)}")
            
            # Convert PyTorch tensor to NumPy array
            if isinstance(audio, torch.Tensor):
                print("Converting PyTorch tensor to NumPy array...")
                audio_numpy = audio.cpu().numpy()
            else:
                audio_numpy = audio
            
            # Save the audio file
            filename = f"kokoro_test_{int(time.time())}.wav"
            sf.write(filename, audio_numpy, 24000)  # Kokoro uses 24kHz sample rate
            print(f"Audio saved to: {filename}")
            return True
            
        return False
    except Exception as e:
        print(f"Error testing Kokoro directly: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_kokoro_directly()
    if success:
        print("Kokoro test completed successfully!")
    else:
        print("Kokoro test failed!")
        sys.exit(1)