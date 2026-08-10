from gtts import gTTS
import os
import time
from typing import Optional
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from services.script_parsing_service import script_parsing_service

class TTSService:
    def __init__(self):
        # Use consolidated directory at the project root level
        self.working_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'work')
        os.makedirs(self.working_dir, exist_ok=True)
    
    def generate_tts(self, text: str, language: str = 'en', filename: str = None) -> Optional[str]:
        """Generate TTS audio from text"""
        try:
            if not filename:
                filename = f"tts_{int(time.time())}.mp3"
            
            filepath = os.path.join(self.working_dir, filename)
            
            # Create gTTS object
            tts = gTTS(text=text, lang=language, slow=False)
            
            # Save to file
            tts.save(filepath)
            
            return filepath
        except Exception as e:
            print(f"Error generating TTS: {e}")
            return None
    
    def generate_script_tts(self, script: str, language: str = 'en') -> Optional[str]:
        """Generate TTS for an entire script"""
        try:
            # Parse the script to extract clean voiceover text
            parsed_script = script_parsing_service.parse_script(script)
            clean_script = script_parsing_service.extract_voiceover_text(parsed_script)
            
            if not clean_script.strip():
                return None
            
            filename = f"script_tts_{int(time.time())}.mp3"
            return self.generate_tts(clean_script, language, filename)
        except Exception as e:
            print(f"Error generating script TTS: {e}")
            return None

# Global instance
tts_service = TTSService()