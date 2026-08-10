import os
import litellm
from src.models.api_key import ApiKey
from src.database import db
from src.services.script_parsing_service import script_parsing_service

# Configure LiteLLM to use the proxy
litellm_proxy_url = os.getenv('LITELLM_PROXY_URL', 'http://localhost:8000')
litellm.api_base = f"{litellm_proxy_url}/v1"
litellm.master_key = "sk-master-key-change-me"  # This should match the master key in config.yaml

class LLMService:
    def __init__(self):
        pass
    
    def add_api_key(self, user_id, name, provider, key):
        """Add a new API key for a user"""
        api_key = ApiKey(
            user_id=user_id,
            name=name,
            provider=provider,
            key=key  # Store directly for now (not encrypted)
        )
        db.session.add(api_key)
        db.session.commit()
        return api_key
    
    def get_user_api_keys(self, user_id):
        """Get all API keys for a user"""
        return ApiKey.query.filter_by(user_id=user_id).all()
    
    def get_active_api_key(self, user_id, provider):
        """Get an active API key for a specific provider"""
        api_key = ApiKey.query.filter_by(
            user_id=user_id, 
            provider=provider, 
            is_active=True
        ).first()
        return api_key
    
    def delete_api_key(self, api_key_id, user_id):
        """Delete an API key"""
        api_key = ApiKey.query.filter_by(id=api_key_id, user_id=user_id).first()
        if api_key:
            db.session.delete(api_key)
            db.session.commit()
            return True
        return False
    
    def configure_litellm(self, user_id):
        """Configure LiteLLM with user's API keys"""
        # Get all active API keys for the user
        api_keys = self.get_user_api_keys(user_id)
        
        # For LiteLLM proxy, we don't need to configure individual keys here
        # The proxy handles routing to the appropriate provider based on the model
        # But we'll keep this method for compatibility
        pass
    
    def generate_script(self, prompt, user_id, model="groq/llama-3.3-70b-versatile", duration=30):
        """Generate a video script using an LLM"""
        try:
            from src.services.video.video_settings import VideoSettings
            
            # Create video settings based on duration
            video_settings = VideoSettings(duration=duration)
            
            # Calculate number of scenes based on duration
            num_scenes = video_settings.get_scene_count()
            
            # Calculate approximate word count based on duration
            words_per_scene = video_settings.get_words_per_scene()
            
            # Create the improved prompt for structured script generation
            full_prompt = f"""\n            Generate a video script for a {duration}-second video based on the following topic: {prompt}\n            \n\n            REQUIREMENTS:\n            1. Create ONE continuous, flowing narrative that tells a complete story from beginning to end\n            2. Write in proper sentences with correct grammar and natural transitions\n            3. Aim for approximately {duration * 2.5} words to fill the {duration} seconds at natural speaking pace\n            4. Divide this continuous narrative into exactly {num_scenes} coherent segments for scenes\n            5. Each scene should naturally flow into the next as part of the same story\n            \n\n            CRITICAL INSTRUCTIONS:\n            - DO NOT create separate clauses or bullet points\n            - DO NOT create fragmented sentences\n            - Write in complete, grammatically correct sentences\n            - Ensure smooth transitions between ideas\n            - The narrative should read like a professional documentary script\n            - Each scene segment should be a natural continuation of the previous one\n            \n\n            OUTPUT FORMAT (Follow this exact format):\n            **Title: \"[Descriptive Title]\"**\n            \n\n            **Full Narrative:**\n            [Write one continuous, flowing narrative with complete sentences that tells a complete story.]\n            \n\n            **Scene Breakdown:**\n            **Scene 1: [Brief Scene Name] (0s-Xs)**\n            ([Detailed visual description for stock footage search])\n            Voiceover: \"[First portion of the continuous narrative - complete sentences that flow naturally]\"\n            \n\n            **Scene 2: [Brief Scene Name] (Ys-Zs)**\n            ([Detailed visual description for stock footage search])\n            Voiceover: \"[Next portion of the continuous narrative - complete sentences that flow naturally from the previous scene]\"\n            \n\n            ... (Continue for all {num_scenes} scenes) ...\n            \n\n            **Scene {num_scenes}: [Brief Scene Name] (Ws-{duration}s)**\n            ([Detailed visual description for stock footage search])\n            Voiceover: \"[Final portion of the continuous narrative - complete sentences that conclude the story]\"\n            \n\n            IMPORTANT GUIDELINES:\n            - The Full Narrative should read as one continuous story\n            - Each scene's Voiceover should be a segment of that continuous story\n            - NEVER create fragmented sentences like \"Ecology advances rapidly\" or \"Microplastic impacts revealed\"\n            - ALWAYS write in complete, grammatically correct sentences\n            - Ensure natural transitions between scenes\n            - Each scene should contribute to the overall narrative arc\n            \n\n            BAD EXAMPLE (DO NOT FOLLOW THIS):\n            **Scene 1: Introduction (0s-3s)**\n            (Animated globe)\n            Voiceover: \"Ecology advances rapidly\"\n            \n\n            **Scene 2: Discovery (3s-6s)**\n            (Researchers in lab)\n            Voiceover: \"Microplastic impacts revealed\"\n            \n\n            GOOD EXAMPLE (FOLLOW THIS FORMAT):\n            **Scene 1: Introduction (0s-3s)**\n            (Animated globe showing ecosystems)\n            Voiceover: \"In 2025, groundbreaking discoveries in ecology are transforming our understanding of the natural world. Scientists are revealing how microplastics are affecting marine ecosystems in ways we never imagined.\"\n            \n\n            **Scene 2: Research Findings (3s-6s)**\n            (Researchers examining samples in laboratory)\n            Voiceover: \"As researchers dive deeper into these findings, they're discovering that these tiny pollutants are disrupting entire food chains, with ripple effects throughout marine environments.\"\n            \n\n            Now generate a script for: {prompt}\n            \n\n            REMEMBER: Write in complete sentences that flow together to tell one continuous story!\n            """
            
            # Call the LLM through the proxy
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=1000,
                temperature=0.7
            )
            
            # Extract the generated script
            script = response.choices[0].message.content
            return script
            
        except Exception as e:
            print(f"Error generating script: {e}")
            # Return a fallback script if LLM fails
            return f"Generated script for: {prompt}\n\nThis is a sample script that would be generated by an LLM based on the user's prompt."

# Global instance
llm_service = LLMService()