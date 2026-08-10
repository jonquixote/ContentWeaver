from typing import Dict, List, Optional, Tuple

class VideoSettings:
    """Configuration class for video generation settings"""
    
    # Supported durations in seconds
    SUPPORTED_DURATIONS = [15, 30, 60, 120, 180, 240, 300]
    
    # Supported resolutions
    SUPPORTED_RESOLUTIONS = [
        # Common resolutions
        (3840, 2160),  # 4K UHD
        (2560, 1440),  # QHD
        (1920, 1080),  # Full HD
        (1280, 720),   # HD
        (854, 480),    # FWVGA
        (640, 360),    # nHD
        (426, 240),    # 240p
    ]
    
    # Supported orientations
    SUPPORTED_ORIENTATIONS = ["landscape", "portrait", "square"]
    
    # Default settings
    DEFAULT_DURATION = 30
    DEFAULT_ORIENTATION = "landscape"
    DEFAULT_WIDTH = 1920
    DEFAULT_HEIGHT = 1080
    
    def __init__(self, duration: int = DEFAULT_DURATION, orientation: str = DEFAULT_ORIENTATION, 
                 width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT):
        """
        Initialize video settings
        
        Args:
            duration: Video duration in seconds
            orientation: Video orientation (landscape, portrait, square)
            width: Video width in pixels
            height: Video height in pixels
        """
        self.duration = self._validate_duration(duration)
        self.orientation = self._validate_orientation(orientation)
        self.width = self._validate_resolution_dimension(width)
        self.height = self._validate_resolution_dimension(height)
        
        # Ensure width and height match the orientation
        self._adjust_resolution_for_orientation()
    
    def _validate_duration(self, duration: int) -> int:
        """Validate and adjust duration to supported values"""
        if duration <= 0:
            return self.DEFAULT_DURATION
            
        # Find the closest supported duration
        closest_duration = min(self.SUPPORTED_DURATIONS, key=lambda x: abs(x - duration))
        return closest_duration
    
    def _validate_orientation(self, orientation: str) -> str:
        """Validate orientation"""
        if orientation.lower() in self.SUPPORTED_ORIENTATIONS:
            return orientation.lower()
        return self.DEFAULT_ORIENTATION
    
    def _validate_resolution_dimension(self, dimension: int) -> int:
        """Validate resolution dimension"""
        if dimension <= 0:
            return self.DEFAULT_WIDTH if dimension == self.width else self.DEFAULT_HEIGHT
            
        # Ensure it's a positive value
        return max(1, dimension)
    
    def _adjust_resolution_for_orientation(self):
        """Adjust resolution dimensions to match orientation"""
        if self.orientation == "landscape":
            # Ensure width >= height
            if self.width < self.height:
                self.width, self.height = self.height, self.width
        elif self.orientation == "portrait":
            # Ensure height >= width
            if self.height < self.width:
                self.width, self.height = self.height, self.width
        elif self.orientation == "square":
            # Make width and height equal (use the larger dimension)
            max_dim = max(self.width, self.height)
            self.width = self.height = max_dim
    
    def get_scene_count(self) -> int:
        """
        Calculate optimal number of scenes based on duration
        Returns 8-15 scenes for 30-second video to achieve 3-4 seconds per clip
        For all videos, aim for higher clip density to ensure better visual variety
        """
        # Target 3-4 seconds per clip (8-15 clips for 30-second video)
        # For 30 seconds: aim for 10 clips (3 seconds each)
        # For 60 seconds: aim for 20 clips (3 seconds each)
        
        # Calculate based on target density of 1 clip per 3 seconds for optimal variety
        target_clips = max(8, self.duration // 3)  # 1 clip per 3 seconds
        
        # Ensure reasonable range based on duration
        # Minimum 8 clips for any video longer than 24 seconds
        min_clips = max(8, self.duration // 4) if self.duration > 24 else 4
        # Maximum 20 clips for 30-second video, 40 for 60-second video
        max_clips = self.duration // 1.5  # At most 1 clip per 1.5 seconds for variety
        
        return max(min_clips, min(max_clips, target_clips))
    
    def get_words_per_scene(self) -> int:
        """
        Calculate approximate words per scene
        Assumes 2.5 words per second for natural speaking pace
        """
        # Target 150 words per minute (2.5 words per second)
        total_words = int(self.duration * 2.5)
        scene_count = self.get_scene_count()
        words_per_scene = total_words // scene_count
        
        # Ensure we have enough words for a natural 3-4 second clip
        # At 2.5 words per second, 3 seconds = 7.5 words, 4 seconds = 10 words
        # We want to aim for 8-12 words per scene to fill 3-4 seconds
        # But allow for more detailed content if the LLM generates it
        return max(8, min(20, words_per_scene))  # 8-20 words per scene for 3-4 second clips
    
    def get_scene_duration(self, scene_index: int) -> Tuple[int, int]:
        """
        Calculate start and end times for a scene
        
        Args:
            scene_index: Zero-based index of the scene
            
        Returns:
            Tuple of (start_time, end_time) in seconds
        """
        scene_count = self.get_scene_count()
        
        if scene_count <= 1:
            return (0, self.duration)
            
        start_time = int((scene_index / scene_count) * self.duration)
        end_time = int(((scene_index + 1) / scene_count) * self.duration)
        
        # Ensure the last scene ends exactly at the total duration
        if scene_index == scene_count - 1:
            end_time = self.duration
            
        return (start_time, end_time)
    
    def to_dict(self) -> Dict:
        """Convert settings to dictionary"""
        return {
            "duration": self.duration,
            "orientation": self.orientation,
            "width": self.width,
            "height": self.height,
            "scene_count": self.get_scene_count(),
            "words_per_scene": self.get_words_per_scene()
        }
    
    @classmethod
    def from_dict(cls, settings_dict: Dict) -> 'VideoSettings':
        """Create VideoSettings from dictionary"""
        return cls(
            duration=settings_dict.get("duration", cls.DEFAULT_DURATION),
            orientation=settings_dict.get("orientation", cls.DEFAULT_ORIENTATION),
            width=settings_dict.get("width", cls.DEFAULT_WIDTH),
            height=settings_dict.get("height", cls.DEFAULT_HEIGHT)
        )

# Global instance with default settings
default_video_settings = VideoSettings()