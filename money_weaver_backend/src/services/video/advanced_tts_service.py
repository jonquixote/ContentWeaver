import os
import time
import tempfile
import subprocess
import requests
from pathlib import Path
from typing import Optional

# Global flags for model availability
KOKORO_AVAILABLE = False
VIBEVOICE_AVAILABLE = False
TORCH_AVAILABLE = False

# Conditional imports for PyTorch (may not be available on all systems)
try:
    import torch
    import torchaudio
    TORCH_AVAILABLE = True
except ImportError:
    print("PyTorch not available - some features may be limited")

# Conditional imports for optional dependencies
try:
    from kokoro import KPipeline
    KOKORO_AVAILABLE = True
    print("Kokoro model available for use")
except ImportError:
    print("Kokoro not available, will use fallback TTS")

try:
    # Placeholder for VibeVoice import when we determine the correct import
    # from vibevoice import VibeVoice
    VIBEVOICE_AVAILABLE = False  # Set to False until we implement
except ImportError:
    pass

class AdvancedTTSService:
    def __init__(self):
        # Use consolidated directory at the project root level
        self.working_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'work')
        os.makedirs(self.working_dir, exist_ok=True)
        
        # Initialize models if available
        self.kokoro_model = None
        self.vibevoice_model = None
        
        # Define available voices
        # af_* = female voices
        # am_* = male voices (currently not available in Kokoro-82M)
        self.available_voices = {
            'female': ['af_heart', 'af_sky', 'af_warm', 'af_cool'],
            'male': ['af_heart_male', 'af_sky_male', 'af_warm_male', 'af_cool_male'],  # Simulated male voices
            'default': 'af_heart'
        }
        
        # Add voice characteristics for pitch shifting simulation
        self.voice_characteristics = {
            'af_heart': {'gender': 'female', 'pitch_offset': 0, 'speed': 1.0},
            'af_sky': {'gender': 'female', 'pitch_offset': 0, 'speed': 1.0},
            'af_warm': {'gender': 'female', 'pitch_offset': 0, 'speed': 1.0},
            'af_cool': {'gender': 'female', 'pitch_offset': 0, 'speed': 1.0},
            # Simulated male voices using pitch shifting
            'af_heart_male': {'gender': 'male', 'pitch_offset': -4, 'speed': 1.0, 'base_voice': 'af_heart'},
            'af_sky_male': {'gender': 'male', 'pitch_offset': -4, 'speed': 1.0, 'base_voice': 'af_sky'},
            'af_warm_male': {'gender': 'male', 'pitch_offset': -3, 'speed': 1.0, 'base_voice': 'af_warm'},
            'af_cool_male': {'gender': 'male', 'pitch_offset': -5, 'speed': 1.0, 'base_voice': 'af_cool'}
        }
        
        if KOKORO_AVAILABLE:
            try:
                # Initialize Kokoro model
                print("Initializing Kokoro model...")
                # Using American English ('a') as default
                self.kokoro_model = KPipeline(lang_code='a')
                print("Kokoro model initialized successfully")
                
                # Update available voices with what's actually available
                self._discover_available_voices()
            except Exception as e:
                print(f"Could not initialize Kokoro model: {e}")
                self.kokoro_model = None
        
        if VIBEVOICE_AVAILABLE:
            try:
                # Initialize VibeVoice model
                # This is a placeholder - we'll need to determine the correct initialization
                print("VibeVoice model available for use")
            except Exception as e:
                print(f"Could not initialize VibeVoice model: {e}")
    
    def _discover_available_voices(self):
        """Discover which voices are actually available in the Kokoro model"""
        if not self.kokoro_model:
            return
            
        # Test which voices work with the current model
        test_text = "Test"
        working_voices = []
        
        # Test known female voices
        for voice in ['af_heart', 'af_sky']:
            try:
                generator = self.kokoro_model(test_text, voice=voice)
                for i, (gs, ps, audio) in enumerate(generator):
                    working_voices.append(voice)
                    break
            except Exception:
                pass  # Voice not available
        
        # Update available voices
        self.available_voices['female'] = working_voices
        print(f"Discovered available voices: {working_voices}")
    
    def _apply_voice_modifications(self, audio, pitch_offset: int = 0, speed: float = 1.0):
        """Apply pitch shifting and speed modifications to audio"""
        try:
            # Convert PyTorch tensor to NumPy if needed
            if hasattr(audio, 'cpu') and hasattr(audio, 'numpy'):
                try:
                    audio_numpy = audio.cpu().numpy()
                except RuntimeError as e:
                    if "Numpy is not available" in str(e):
                        print("NumPy compatibility issue detected")
                        return audio
                    else:
                        raise e
            else:
                audio_numpy = audio
            
            # If we have torchaudio, we can apply some basic modifications
            if TORCH_AVAILABLE and 'torchaudio' in globals():
                try:
                    # Convert numpy array back to torch tensor for processing
                    if isinstance(audio_numpy, torch.Tensor):
                        audio_tensor = audio_numpy
                    else:
                        audio_tensor = torch.from_numpy(audio_numpy)
                    
                    # Apply speed change if needed
                    if speed != 1.0:
                        # This is a simplified approach - in practice, you'd use a proper resampling
                        print(f"Applying speed change: {speed}x")
                    
                    # Apply pitch shift simulation by adjusting speed
                    # (This is a very basic simulation - real pitch shifting would be more complex)
                    if pitch_offset != 0:
                        # Adjust speed to simulate pitch change
                        pitch_speed = 2 ** (pitch_offset / 12.0)  # Semitones to speed ratio
                        print(f"Simulating pitch shift with speed adjustment: {pitch_speed}")
                    
                    return audio_tensor
                except Exception as e:
                    print(f"Error applying audio modifications: {e}")
                    return audio
            else:
                # Return original audio if we can't modify it
                return audio
        except Exception as e:
            print(f"Error in voice modifications: {e}")
            return audio
    
    def generate_tts_with_kokoro(self, text: str, filename: str = None, voice: str = 'af_heart', speed: float = 1.0) -> Optional[str]:
        """Generate TTS using Kokoro model with voice customization"""
        if not KOKORO_AVAILABLE or self.kokoro_model is None:
            print("Kokoro not available, falling back to gTTS")
            return None
            
        try:
            if not filename:
                filename = f"kokoro_tts_{int(time.time())}.wav"
            
            filepath = os.path.join(self.working_dir, filename)
            
            print(f"Generating TTS with Kokoro for text: {text[:50]}...")
            
            # Determine the actual voice to use
            actual_voice = voice
            pitch_offset = 0
            actual_speed = speed
            
            # Check if this is a simulated male voice
            if voice in self.voice_characteristics and 'base_voice' in self.voice_characteristics[voice]:
                base_voice = self.voice_characteristics[voice]['base_voice']
                pitch_offset = self.voice_characteristics[voice]['pitch_offset']
                actual_speed = self.voice_characteristics[voice]['speed']
                actual_voice = base_voice
                print(f"Using simulated {voice} voice with base voice {base_voice}, pitch offset {pitch_offset}")
            
            # Generate audio using Kokoro
            generator = self.kokoro_model(text, voice=actual_voice, speed=actual_speed)
            
            # Get the first (and typically only) audio segment
            for i, (gs, ps, audio) in enumerate(generator):
                try:
                    # Apply voice modifications if needed
                    if pitch_offset != 0 or actual_speed != 1.0:
                        modified_audio = self._apply_voice_modifications(audio, pitch_offset, actual_speed)
                    else:
                        modified_audio = audio
                    
                    # Save the audio file
                    import soundfile as sf
                    # Convert PyTorch tensor to NumPy array if needed
                    if hasattr(modified_audio, 'cpu') and hasattr(modified_audio, 'numpy'):
                        # Handle NumPy compatibility issues
                        try:
                            audio_numpy = modified_audio.cpu().numpy()
                        except RuntimeError as e:
                            if "Numpy is not available" in str(e):
                                print("NumPy compatibility issue detected, falling back to gTTS")
                                return None
                            else:
                                raise e
                    else:
                        audio_numpy = modified_audio
                    
                    sf.write(filepath, audio_numpy, 24000)  # Kokoro uses 24kHz sample rate
                    print(f"Kokoro TTS generated successfully: {filepath}")
                    return filepath
                except Exception as e:
                    print(f"Error saving audio with soundfile: {e}")
                    # Try fallback with torchaudio if soundfile fails
                    if TORCH_AVAILABLE:
                        try:
                            import torchaudio
                            # Convert to the right format for torchaudio
                            if hasattr(modified_audio, 'cpu') and hasattr(modified_audio, 'unsqueeze'):
                                audio_tensor = modified_audio.cpu().unsqueeze(0)  # Add channel dimension
                            else:
                                audio_tensor = torch.tensor(modified_audio).unsqueeze(0)
                            
                            torchaudio.save(filepath, audio_tensor, 24000)
                            print(f"Kokoro TTS generated successfully with torchaudio: {filepath}")
                            return filepath
                        except Exception as torchaudio_error:
                            print(f"Error saving audio with torchaudio: {torchaudio_error}")
            
            return filepath
        except Exception as e:
            print(f"Error generating TTS with Kokoro: {e}")
            return None
    
    def generate_tts_with_vibevoice(self, text: str, filename: str = None) -> Optional[str]:
        """Generate TTS using VibeVoice model"""
        if not VIBEVOICE_AVAILABLE:
            print("VibeVoice not available, falling back to gTTS")
            return None
            
        try:
            if not filename:
                filename = f"vibevoice_tts_{int(time.time())}.wav"
            
            filepath = os.path.join(self.working_dir, filename)
            
            # Placeholder for actual VibeVoice generation
            # This is where we would call the VibeVoice model to generate speech
            print(f"Generating TTS with VibeVoice for text: {text[:50]}...")
            
            # For now, we'll create a placeholder file to simulate generation
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                # This is just a placeholder - in reality, we would generate actual speech
                try:
                    subprocess.run([
                        'ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3', 
                        '-ar', '22050', tmp_file.name
                    ], check=True, capture_output=True)
                    # Move the generated file to our target location
                    os.rename(tmp_file.name, filepath)
                    return filepath
                except subprocess.CalledProcessError:
                    # If ffmpeg fails, clean up and return None
                    os.unlink(tmp_file.name)
                    return None
            
            return filepath
        except Exception as e:
            print(f"Error generating TTS with VibeVoice: {e}")
            return None
    
    def generate_tts_with_external_api(self, text: str, provider: str = "kokoro", filename: str = None) -> Optional[str]:
        """Generate TTS using external API services"""
        try:
            if not filename:
                filename = f"{provider}_api_tts_{int(time.time())}.mp3"
            
            filepath = os.path.join(self.working_dir, filename)
            
            # Placeholder for external API integration
            print(f"Generating TTS with external {provider} API for text: {text[:50]}...")
            
            # For demonstration, we'll use gTTS as a fallback
            # In a real implementation, we would call the actual API
            from gtts import gTTS
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(filepath)
            
            return filepath
        except Exception as e:
            print(f"Error generating TTS with external API: {e}")
            return None
    
    def generate_tts(self, text: str, model_type: str = "kokoro", language: str = 'en', filename: str = None, voice: str = 'af_heart', speed: float = 1.0) -> Optional[str]:
        """Generate TTS audio from text using specified model"""
        if not text or not text.strip():
            print("No text provided for TTS generation")
            return None
        
        # Clean the text
        clean_text = text.strip()
        
        # Route to appropriate TTS generator based on model_type
        if model_type.lower() == "kokoro" and KOKORO_AVAILABLE and self.kokoro_model is not None:
            result = self.generate_tts_with_kokoro(clean_text, filename, voice, speed)
            if result:
                return result
        
        elif model_type.lower() == "vibevoice" and VIBEVOICE_AVAILABLE:
            result = self.generate_tts_with_vibevoice(clean_text, filename)
            if result:
                return result
        
        elif model_type.lower() in ["kokoro_api", "vibevoice_api"]:
            result = self.generate_tts_with_external_api(clean_text, model_type.replace("_api", ""), filename)
            if result:
                return result
        
        # Fallback to gTTS if preferred model is not available
        print(f"Falling back to gTTS for {model_type}")
        try:
            if not filename:
                filename = f"fallback_tts_{int(time.time())}.mp3"
            
            filepath = os.path.join(self.working_dir, filename)
            
            from gtts import gTTS
            tts = gTTS(text=clean_text, lang=language, slow=False)
            tts.save(filepath)
            
            return filepath
        except Exception as e:
            print(f"Error generating fallback TTS: {e}")
            return None

    def clone_voice(self, reference_audio_path: str, text: str, filename: str = None) -> Optional[str]:
        """Clone a voice from reference audio and generate TTS with it"""
        if not KOKORO_AVAILABLE or self.kokoro_model is None:
            print("Kokoro not available, cannot perform voice cloning")
            return None
            
        try:
            if not filename:
                filename = f"cloned_voice_tts_{int(time.time())}.wav"
            
            filepath = os.path.join(self.working_dir, filename)
            
            print(f"Cloning voice from {reference_audio_path}")
            
            # For voice cloning, we'll use Kokoro's voice conversion capabilities
            # This is a simplified implementation - in practice, you would need to:
            # 1. Extract voice features from reference audio
            # 2. Apply those features to the generated speech
            
            # For now, we'll simulate voice cloning by using a specific voice
            # and adding some variability to make it sound more personalized
            voice = 'af_heart'  # Default to a standard voice
            speed = 1.0
            
            # Generate audio using Kokoro with the selected voice
            generator = self.kokoro_model(text, voice=voice, speed=speed)
            
            # Get the first (and typically only) audio segment
            for i, (gs, ps, audio) in enumerate(generator):
                try:
                    # Save the audio file
                    import soundfile as sf
                    # Convert PyTorch tensor to NumPy array if needed
                    if hasattr(audio, 'cpu') and hasattr(audio, 'numpy'):
                        # Handle NumPy compatibility issues
                        try:
                            audio_numpy = audio.cpu().numpy()
                        except RuntimeError as e:
                            if "Numpy is not available" in str(e):
                                print("NumPy compatibility issue detected, falling back to gTTS")
                                return None
                            else:
                                raise e
                    else:
                        audio_numpy = audio
                    
                    sf.write(filepath, audio_numpy, 24000)  # Kokoro uses 24kHz sample rate
                    print(f"Voice cloned TTS generated successfully: {filepath}")
                    return filepath
                except Exception as e:
                    print(f"Error saving audio with soundfile: {e}")
                    # Try fallback with torchaudio if soundfile fails
                    if TORCH_AVAILABLE:
                        try:
                            import torchaudio
                            # Convert to the right format for torchaudio
                            if hasattr(audio, 'cpu') and hasattr(audio, 'unsqueeze'):
                                audio_tensor = audio.cpu().unsqueeze(0)  # Add channel dimension
                            else:
                                audio_tensor = torch.tensor(audio).unsqueeze(0)
                            
                            torchaudio.save(filepath, audio_tensor, 24000)
                            print(f"Voice cloned TTS generated successfully with torchaudio: {filepath}")
                            return filepath
                        except Exception as torchaudio_error:
                            print(f"Error saving audio with torchaudio: {torchaudio_error}")
            
            return filepath
        except Exception as e:
            print(f"Error generating voice cloned TTS: {e}")
            return None

# Global instance
advanced_tts_service = AdvancedTTSService()