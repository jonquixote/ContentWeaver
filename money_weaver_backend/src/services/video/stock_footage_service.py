import requests
import os
import random
from typing import List, Dict, Tuple
import time
import cv2
import sys
import re
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from services.script_parsing_service import script_parsing_service

class StockFootageService:
    def __init__(self):
        self.pexels_api_key = os.getenv('PEXELS_API_KEY')
        self.pixabay_api_key = os.getenv('PIXABAY_API_KEY')
        # Use consolidated directory at the project root level
        self.working_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'work')
        os.makedirs(self.working_dir, exist_ok=True)
        # For testing, we'll use sample videos if no API keys are configured
        self.use_sample_videos = not (self.pexels_api_key or self.pixabay_api_key)
    
    def _extract_keywords(self, text: str, max_keywords: int = 3) -> List[str]:
        """
        Extract relevant keywords from text for stock footage search
        """
        if not text:
            return []
        
        # Remove common generic phrases
        generic_phrases = [
            "general visuals", "general", "scene", "visuals", "this scene", 
            "for this", "depicting", "showing", "featuring", "related to"
        ]
        
        # Clean the text
        cleaned_text = text.lower()
        for phrase in generic_phrases:
            cleaned_text = cleaned_text.replace(phrase, "")
        
        # Remove extra whitespace and punctuation
        cleaned_text = re.sub(r'[^\w\s]', ' ', cleaned_text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        # Split into words
        words = cleaned_text.split()
        
        # Filter out common stop words but keep meaningful ones
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 
            'after', 'above', 'below', 'between', 'among', 'is', 'are', 'was', 
            'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
            'this', 'that', 'these', 'those', 'a', 'an', 'as', 'so', 'if', 'it'
        }
        
        # Keep only meaningful words (not stop words and longer than 2 characters)
        meaningful_words = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Return unique keywords, limited to max_keywords
        return list(dict.fromkeys(meaningful_words))[:max_keywords]
    
    def _generate_search_queries(self, shot_description: str, voiceover_text: str, max_queries: int = 3) -> List[str]:
        """
        Generate search queries based on shot description and voiceover text
        """
        queries = []
        
        # Extract keywords from shot description
        shot_keywords = self._extract_keywords(shot_description, 2)
        if shot_keywords:
            queries.append(" ".join(shot_keywords))
        
        # Extract keywords from voiceover text
        voiceover_keywords = self._extract_keywords(voiceover_text, 2)
        if voiceover_keywords:
            queries.append(" ".join(voiceover_keywords))
        
        # Combine shot and voiceover keywords
        if shot_keywords and voiceover_keywords:
            combined_keywords = list(dict.fromkeys(shot_keywords + voiceover_keywords))[:3]
            queries.append(" ".join(combined_keywords))
        
        # If we still don't have good queries, use some fallback strategies
        if not queries or all(q in ["general", "scene", "visuals"] for q in queries):
            # Extract nouns and verbs from voiceover as fallback
            fallback_keywords = self._extract_keywords(voiceover_text, 3)
            if fallback_keywords:
                queries.append(" ".join(fallback_keywords))
        
        # Remove duplicates and limit
        unique_queries = list(dict.fromkeys(queries))[:max_queries]
        return unique_queries if unique_queries else ["nature"]  # Fallback to "nature"
    
    def search_pexels_videos(self, query: str, per_page: int = 5, orientation: str = "landscape", min_width: int = 1280, min_height: int = 720) -> List[Dict]:
        """Search for videos on Pexels with resolution and orientation parameters"""
        if not self.pexels_api_key:
            print("Warning: Pexels API key not configured")
            return []
        
        try:
            # Map orientation values for Pexels API
            pexels_orientation = "landscape"  # Default
            if orientation == "portrait":
                pexels_orientation = "portrait"
            elif orientation == "square":
                pexels_orientation = "square"
            # landscape remains as "landscape"
            
            url = "https://api.pexels.com/videos/search"
            headers = {"Authorization": self.pexels_api_key}
            params = {
                "query": query,
                "per_page": per_page,
                "orientation": pexels_orientation,
                "min_width": min_width,
                "min_height": min_height
            }
            
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get('videos', [])[:per_page]
        except Exception as e:
            print(f"Error searching Pexels videos: {e}")
        
        return []
    
    def search_pixabay_videos(self, query: str, per_page: int = 5, orientation: str = "horizontal", min_width: int = 1280, min_height: int = 720) -> List[Dict]:
        """Search for videos on Pixabay with resolution and orientation parameters"""
        if not self.pixabay_api_key:
            print("Warning: Pixabay API key not configured")
            return []
        
        try:
            # Map orientation values for Pixabay API
            pixabay_orientation = "horizontal"  # Default
            if orientation == "portrait":
                pixabay_orientation = "vertical"
            elif orientation == "square":
                # For square, we can use either horizontal or vertical and crop later
                pixabay_orientation = "horizontal"
            # landscape maps to "horizontal"
            
            url = "https://pixabay.com/api/videos/"
            params = {
                "key": self.pixabay_api_key,
                "q": query,
                "per_page": per_page,
                "video_type": "film",
                "orientation": pixabay_orientation,
                "min_width": min_width,
                "min_height": min_height
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get('hits', [])[:per_page]
        except Exception as e:
            print(f"Error searching Pixabay videos: {e}")
        
        return []
    
    def get_video_duration(self, video_path: str) -> float:
        """Get the duration of a video file in seconds"""
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frame_count / fps
            cap.release()
            return duration
        except Exception as e:
            print(f"Error getting video duration: {e}")
            return 0.0
    
    def download_video(self, video_url: str, filename: str) -> str:
        """Download a video file"""
        try:
            filepath = os.path.join(self.working_dir, filename)
            
            # Check if file already exists
            if os.path.exists(filepath):
                return filepath
            
            response = requests.get(video_url, stream=True)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return filepath
        except Exception as e:
            print(f"Error downloading video: {e}")
        
        return None
    
    def get_stock_videos_for_script(self, script: str, target_scenes: List[Dict] = None, max_videos: int = 10, 
                                   orientation: str = "landscape", min_width: int = 1280, min_height: int = 720) -> List[Tuple[str, float, Dict]]:
        """
        Get stock videos based on script content with duration information and resolution settings
        
        Returns:
            List[Tuple[video_path, duration, scene_info]]
        """
        print(f"Getting stock videos for script (max_videos={max_videos}, orientation={orientation}, min_width={min_width}, min_height={min_height})")
        # If we're in testing mode (no API keys), use sample videos
        if self.use_sample_videos:
            print("Using sample videos for testing")
            return self._get_sample_videos_with_duration(max_videos)
        
        # Parse script to get shot descriptions if target_scenes not provided
        if target_scenes is None:
            parsed_script = script_parsing_service.parse_script(script)
            scenes = parsed_script.get('scenes', [])
        else:
            scenes = target_scenes
        
        print(f"Processing {len(scenes)} scenes")
        
        video_files = []
        downloaded_count = 0
        used_video_urls = set()  # Track URLs to prevent duplicates
        
        for i, scene in enumerate(scenes):
            if downloaded_count >= max_videos:
                break
                
            shot_desc = scene.get('visual_description', '')
            voiceover_text = scene.get('voiceover', '')
            
            print(f"Processing scene {i+1}: {shot_desc}")
            print(f"Voiceover text: {voiceover_text}")
            
            # Generate better search queries
            search_queries = self._generate_search_queries(shot_desc, voiceover_text, 3)
            print(f"Generated search queries: {search_queries}")
            
            # Try each query until we find videos
            all_videos = []
            for query in search_queries:
                if len(all_videos) >= 6:  # Limit total videos per scene
                    break
                    
                print(f"Searching for videos with query: {query}")
                # Search on both platforms with resolution and orientation parameters
                pexels_videos = self.search_pexels_videos(query, 3, orientation, min_width, min_height)
                pixabay_videos = self.search_pixabay_videos(query, 3, orientation, min_width, min_height)
                print(f"Found {len(pexels_videos)} Pexels videos and {len(pixabay_videos)} Pixabay videos")
                
                # Combine results
                scene_videos = pexels_videos + pixabay_videos
                
                # Add scene context to each video
                for video_data in scene_videos:
                    video_data['_scene_context'] = {
                        'query': query,
                        'scene_index': i,
                        'scene_description': shot_desc
                    }
                
                all_videos.extend(scene_videos)
            
            # Shuffle to add randomness
            random.shuffle(all_videos)
            
            # Process videos, avoiding duplicates
            for video_data in all_videos:
                if downloaded_count >= max_videos:
                    break
                
                # Get video URL and metadata
                video_url = None
                video_metadata = {}
                
                if 'video_files' in video_data:  # Pexels format
                    # Get the best quality video file
                    best_file = None
                    for file_info in video_data['video_files']:
                        # Prefer HD quality (1280x720 or higher)
                        if file_info.get('width', 0) >= 1280 and file_info.get('height', 0) >= 720:
                            if not best_file or file_info.get('width', 0) > best_file.get('width', 0):
                                best_file = file_info
                    
                    # If no HD quality found, get the first available
                    if not best_file and video_data['video_files']:
                        best_file = video_data['video_files'][0]
                    
                    if best_file:
                        video_url = best_file['link']
                        video_metadata = {
                            'width': best_file.get('width', 0),
                            'height': best_file.get('height', 0),
                            'fps': best_file.get('fps', 30),
                            'file_type': best_file.get('file_type', 'video/mp4'),
                            'quality': best_file.get('quality', 'unknown')
                        }
                    
                    # Add Pexels-specific metadata
                    video_metadata.update({
                        'pexels_id': video_data.get('id'),
                        'pexels_duration': video_data.get('duration', 0),
                        'pexels_width': video_data.get('width', 0),
                        'pexels_height': video_data.get('height', 0),
                        'description': shot_desc,
                        'source': 'pexels',
                        'search_query': video_data.get('_scene_context', {}).get('query', ''),
                        'scene_index': video_data.get('_scene_context', {}).get('scene_index', -1)
                    })
                elif 'videos' in video_data:  # Pixabay format
                    # Pixabay returns a dict with quality keys like 'large', 'medium', etc.
                    if video_data['videos']:
                        # Prefer large quality, fallback to medium, then small
                        videos_dict = video_data['videos']
                        selected_quality = None
                        video_info = None
                        
                        if 'large' in videos_dict:
                            selected_quality = 'large'
                            video_info = videos_dict['large']
                        elif 'medium' in videos_dict:
                            selected_quality = 'medium'
                            video_info = videos_dict['medium']
                        elif 'small' in videos_dict:
                            selected_quality = 'small'
                            video_info = videos_dict['small']
                        else:
                            # Get first available quality
                            first_quality = next(iter(videos_dict), None)
                            if first_quality and isinstance(videos_dict[first_quality], dict):
                                selected_quality = first_quality
                                video_info = videos_dict[first_quality]
                        
                        if video_info:
                            video_url = video_info.get('url')
                            video_metadata = {
                                'width': video_info.get('width', 0),
                                'height': video_info.get('height', 0),
                                'quality': selected_quality,
                                'file_type': 'video/mp4',
                                'description': shot_desc,
                                'source': 'pixabay',
                                'pixabay_id': video_data.get('id'),
                                'pixabay_duration': video_data.get('duration', 0),
                                'pixabay_tags': video_data.get('tags', ''),
                                'search_query': video_data.get('_scene_context', {}).get('query', ''),
                                'scene_index': video_data.get('_scene_context', {}).get('scene_index', -1)
                            }
                
                # Check if we have a valid URL and it hasn't been used recently
                if video_url and video_url not in used_video_urls:
                    print(f"Downloading video from: {video_url}")
                    filename = f"stock_{int(time.time())}_{downloaded_count}.mp4"
                    filepath = self.download_video(video_url, filename)
                    if filepath:
                        print(f"Downloaded video to: {filepath}")
                        # Get video duration using metadata if available, otherwise calculate
                        duration = video_metadata.get('pexels_duration') or video_metadata.get('pixabay_duration') or self.get_video_duration(filepath)
                        print(f"Video duration: {duration} seconds")
                        
                        # Add the actual file duration to metadata
                        video_metadata['actual_duration'] = duration
                        video_metadata['file_path'] = filepath
                        
                        video_files.append((filepath, duration, video_metadata))
                        used_video_urls.add(video_url)  # Track this URL
                        downloaded_count += 1
                    else:
                        print("Failed to download video")
                elif video_url in used_video_urls:
                    print(f"Skipping duplicate video: {video_url}")
                else:
                    print("No video URL found")
        
        print(f"Returning {len(video_files)} video files with duration info")
        return video_files
    
    def _get_sample_videos_with_duration(self, max_videos: int = 10) -> List[Tuple[str, float, Dict]]:
        """Get sample videos for testing when no API keys are configured"""
        print("Using sample videos for testing (no API keys configured)")
        
        # Look for sample videos in the work directory
        sample_videos = []
        for filename in os.listdir(self.working_dir):
            if filename.startswith('sample') and filename.endswith('.mp4'):
                filepath = os.path.join(self.working_dir, filename)
                duration = self.get_video_duration(filepath)
                sample_videos.append((filepath, duration, {
                    'description': 'sample video', 
                    'source': 'local',
                    'actual_duration': duration,
                    'file_path': filepath,
                    'width': 1280,
                    'height': 720,
                    'fps': 30
                }))
        
        # If we don't have enough sample videos, create more
        while len(sample_videos) < max_videos:
            index = len(sample_videos) + 1
            sample_file = os.path.join(self.working_dir, f'sample{index}.mp4')
            
            # If the file doesn't exist, create it
            if not os.path.exists(sample_file):
                self._create_sample_video(sample_file)
            
            duration = self.get_video_duration(sample_file)
            sample_videos.append((sample_file, duration, {
                'description': 'sample video', 
                'source': 'local',
                'actual_duration': duration,
                'file_path': sample_file,
                'width': 1280,
                'height': 720,
                'fps': 30
            }))
        
        return sample_videos[:max_videos]
    
    def _create_sample_video(self, filepath: str):
        """Create a sample video file for testing"""
        try:
            # Create a simple test video using ffmpeg
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file
                '-f', 'lavfi',
                '-i', 'testsrc2=duration=5:size=1280x720:rate=30',
                '-vf', f'hue=s={random.random()}',  # Add some variation
                filepath
            ]
            
            import subprocess
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error creating sample video: {result.stderr}")
        except Exception as e:
            print(f"Error creating sample video: {e}")

# Global instance
stock_service = StockFootageService()