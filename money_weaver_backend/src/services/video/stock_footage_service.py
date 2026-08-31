import requests
import os
import random
from typing import List, Dict, Tuple, Optional
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
    
    # Words that describe mood/lighting/motion rather than a searchable visual
    # subject. Keyword extraction should avoid these so queries return real
    # footage instead of "dimly lit" -> random close-ups.
    _WEAK_VISUAL_WORDS = {
        "dimly", "lit", "filled", "bustling", "quiet", "dark", "bright", "large",
        "small", "little", "emotional", "hopeful", "nervous", "tense", "slow",
        "fast", "cinematic", "dramatic", "beautiful", "general", "some", "various",
        "many", "two", "three", "the", "this", "that", "these", "those",
    }

    def _extract_keywords(self, text: str, max_keywords: int = 3) -> List[str]:
        """Extract concrete, searchable visual keywords from a shot description.

        Prefers noun phrases (e.g. \"comedy club\") and substantive nouns over
        generic mood/lighting words, so stock searches return relevant footage.
        """
        if not text:
            return []

        # Clean the text: lowercase, strip punctuation, collapse whitespace
        cleaned_text = re.sub(r'[^\w\s]', ' ', text.lower())
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        words = cleaned_text.split()

        # Keep meaningful content words (not stop words / weak visual fillers)
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before',
            'after', 'above', 'below', 'between', 'among', 'is', 'are', 'was',
            'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
            'an', 'as', 'so', 'if', 'it', 'a',
        }
        meaningful = [
            w for w in words
            if w not in stop_words and len(w) > 2 and w not in self._WEAK_VISUAL_WORDS
        ]

        # Build phrase candidates first (adjacent meaningful pairs), then singles.
        phrases = [f"{a} {b}" for a, b in zip(meaningful, meaningful[1:])]
        candidates = list(dict.fromkeys(phrases + meaningful))
        return candidates[:max_keywords]
    
    def _generate_search_queries(self, shot_description: str, voiceover_text: str, max_queries: int = 3) -> List[str]:
        """
        Generate search queries based on shot description and voiceover text
        """
        queries = []
        shot_keywords = self._extract_keywords(shot_description, 3)
        voiceover_keywords = self._extract_keywords(voiceover_text, 2)

        if shot_keywords:
            queries.append(shot_keywords[0])
        if voiceover_keywords and voiceover_keywords[0] not in queries:
            queries.append(voiceover_keywords[0])
        if len(shot_keywords) > 1:
            queries.append(shot_keywords[1])

        # Remove duplicates and limit
        unique_queries = list(dict.fromkeys(queries))[:max_queries]
        return unique_queries if unique_queries else ["nature"]  # Fallback to "nature"

    def _llm_scene_queries(self, scenes: List[Dict]) -> Dict[int, List[str]]:
        """Generate on-theme stock-video search phrases per scene with the LLM.

        Returns {scene_index: [query, ...]} so each scene searches with a
        concrete, visual query (real places/objects/people/actions) instead of
        naive keyword extraction. Returns {} on any failure so callers fall back.
        """
        try:
            from services.llm_service import llm_service
        except Exception as e:
            print(f"LLM query generation unavailable: {e}")
            return {}

        descriptors = []
        for i, s in enumerate(scenes):
            visual = (s.get('visual_description') or s.get('description') or '').strip()
            voice = (s.get('voiceover') or '').strip()
            descriptors.append(f"Scene {i}: VISUAL: {visual} | VOICEOVER: {voice}")

        if not descriptors:
            return {}

        prompt = (
            "You generate stock-video footage search phrases. For each scene, give 1-2 short "
            "search queries (each <=6 words) that describe CONCRETE, SEARCHABLE visual content the "
            "camera shows: real places, objects, people, actions. Do NOT describe emotions, metaphors, "
            "story meaning, or paraphrase the voiceover. Do NOT use placeholders. Return ONLY JSON:\n"
            '{"queries":[{"scene":0,"query":["comedy club stage","audience laughing"]},'
            '{"scene":1,"query":["stand up comedian microphone"]}]}\n\n'
            "SCENES:\n" + "\n".join(descriptors)
        )

        try:
            model = os.getenv("SCRIPT_MODEL") or "openai/gpt-4o-mini"
            raw = llm_service._chat_free_resilient(
                None, model, [{"role": "user", "content": prompt}],
                max_tokens=1600, temperature=0.2)
            data = llm_service._extract_json(raw)
            if not isinstance(data, dict):
                return {}
            out = {}
            for entry in data.get('queries', []):
                scene = entry.get('scene')
                qs = [str(q).strip() for q in (entry.get('query') or []) if str(q).strip()]
                if isinstance(scene, int) and qs:
                    out[scene] = qs[:3]
            return out
        except Exception as e:
            print(f"LLM query generation failed: {e}")
            return {}

    @staticmethod
    def _preview_url(video_data) -> Optional[str]:
        """A publicly fetchable preview thumbnail for a search result item,
        used to vision-verify the clip is on-theme before downloading it."""
        img = video_data.get('image')
        if isinstance(img, str) and img.startswith('http'):
            return img
        return None

    def _vision_score(self, image_url, description, voiceover):
        """0-5 relevance that a clip matches the scene; None on any failure."""
        if not image_url:
            return None
        try:
            import json as _json
            import re as _re
            payload = {
                'model': os.getenv('VISION_MODEL') or 'openai/gpt-4o-mini',
                'messages': [{'role': 'user', 'content': [
                    {'type': 'image_url', 'image_url': {'url': image_url}},
                    {'type': 'text', 'text': (
                        'You judge whether a stock-video thumbnail matches a scene. '
                        'Reject clips that show something clearly unrelated to the scene '
                        '(e.g. an animal or unrelated subject when the scene needs a person on a stage). '
                        f'Scene shows: {description}. Voiceover: {voiceover}. '
                        'Reply ONLY JSON: {"on_theme": true/false, "relevance": 0-5}. '
                        'Set on_theme=false only when clearly unrelated.')},
                ]}],
                'max_tokens': 60,
            }
            r = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                json=payload,
                headers={'Authorization': 'Bearer ' + (os.getenv('OPENROUTER_API_KEY') or '')},
                timeout=60)
            if r.status_code != 200:
                return None
            content = r.json()['choices'][0]['message']['content']
            m = _re.search(r'\{.*\}', content, _re.DOTALL)
            if not m:
                return None
            d = _json.loads(m.group(0))
            if not isinstance(d, dict):
                return None
            if d.get('on_theme') is False:
                return 0
            return max(0, int(d.get('relevance') or 3))
        except Exception as e:
            print(f"vision score failed: {e}")
            return None

    def _rerank_candidates(self, all_videos, description, voiceover):
        """Drop off-theme candidates and order the rest by relevance.

        Candidates without a usable thumbnail are kept (not dropped) but sorted
        after validated ones, so we never over-filter to an empty scene."""
        scored = []
        for v in all_videos:
            img = self._preview_url(v)
            score = self._vision_score(img, description, voiceover) if img else None
            if score is not None and score < 2:
                continue  # clearly off-theme, drop it
            scored.append((v, score))

        def key(item):
            s = item[1]
            if s is None:
                return (2, 0)  # unvalidated: keep, but after validated on-theme
            return (0, -s)     # validated: higher relevance first

        scored.sort(key=key)
        return [v for v, _ in scored]

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

        # Generate on-theme, per-scene search queries once up front (LLM),
        # falling back to naive keyword extraction per scene if it fails.
        queries_by_scene = self._llm_scene_queries(scenes)

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
            search_queries = queries_by_scene.get(i) or self._generate_search_queries(shot_desc, voiceover_text, 3)
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
            
            # Vision-rerank candidates: drop off-theme clips (e.g. an animal when
            # the scene needs a person on a stage) and order the rest by relevance.
            # Falls back to the gathered order (shuffled) when the LLM is
            # unavailable so a scene is never left empty.
            try:
                all_videos = self._rerank_candidates(all_videos, shot_desc, voiceover_text)
                print(f"Reranked scene {i+1} to {len(all_videos)} on-theme candidates")
            except Exception as e:
                print(f"Rerank failed for scene {i+1}, keeping original order: {e}")
                random.shuffle(all_videos)
            
            # Process videos, avoiding duplicates
            for video_data in all_videos:
                if downloaded_count >= max_videos:
                    break
                
                # Get video URL and metadata
                video_url = None
                video_metadata = {}
                
                if 'video_files' in video_data:  # Pexels format
                    # Choose the file closest to the target height, but never
                    # 4K+ — avoids huge downloads that can fill the disk.
                    target_h = min_height or 720
                    best_file = None
                    for file_info in video_data['video_files']:
                        h = file_info.get('height', 0)
                        if h > 2160:
                            continue
                        if best_file is None:
                            best_file = file_info
                            continue
                        bh = best_file.get('height', 0)
                        chosen = abs(h - target_h) < abs(bh - target_h) or (
                            abs(h - target_h) == abs(bh - target_h) and h < bh)
                        if chosen:
                            best_file = file_info
                    
                    # If no reasonable-sized file found, use the first available
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