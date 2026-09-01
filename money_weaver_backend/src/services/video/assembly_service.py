import subprocess
import os
import time
import random
import re
from typing import List, Optional, Tuple, Dict

# No sys.path hack needed; relative import works when module is used properly
# (same package directory)

_CAPTION_COLORS = {
    'white': (255, 255, 255, 255),
    'black': (0, 0, 0, 255),
    'yellow': (255, 255, 0, 255),
    'red': (255, 0, 0, 255),
    'green': (0, 255, 0, 255),
    'blue': (0, 0, 255, 255),
    'cyan': (0, 255, 255, 255),
    'magenta': (255, 0, 255, 255),
}


def _font_path_for(name: str, bold: bool) -> str:
    """Find a TTF font file for the given name and weight, cross-platform."""
    name = str(name or 'Arial')
    candidates = []
    # Common font directories across platforms
    font_dirs = [
        '/System/Library/Fonts/Supplemental',          # macOS
        '/System/Library/Fonts',                       # macOS
        '/Library/Fonts',                              # macOS
        '/usr/share/fonts/truetype',                   # Linux
        '/usr/share/fonts',                            # Linux
        '/usr/local/share/fonts',                      # Linux
        os.path.join(os.environ.get('WINDIR', ''), 'Fonts') if os.name == 'nt' else None,  # Windows
    ]
    font_dirs = [d for d in font_dirs if d and os.path.isdir(d)]
    # Build candidate paths. For bold, check bold variants first so a plain
    # file like "Arial.ttf" never shadows "Arial Bold.ttf" (otherwise **bold**
    # markers silently render regular).
    if bold:
        for base in [' Bold', ' Bold Italic', 'Bold', 'Bold Italic', '']:
            for d in font_dirs:
                candidates.append(os.path.join(d, f"{name}{base}.ttf"))
                candidates.append(os.path.join(d, f"{name}{base}.ttc"))
    else:
        for base in ['', ' Italic ', ' Bold ']:
            for d in font_dirs:
                candidates.append(os.path.join(d, f"{name}{base}.ttf"))
                candidates.append(os.path.join(d, f"{name}{base}.ttc"))
    # Fallback common font files
    for d in font_dirs:
        candidates.append(os.path.join(d, 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'))
        candidates.append(os.path.join(d, 'Arial Bold.ttf' if bold else 'Arial.ttf'))
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    # Last resort: use PIL's default (no bold)
    return ''  # will raise in truetype(), caller handles fallback


def _render_caption_png(text: str, font_size: int, color, border: int,
                        regular_path: str, bold_path: str, width: int, height: int) -> Optional[str]:
    from PIL import Image, ImageDraw, ImageFont
    # Load fonts with fallback
    try:
        regular_font = ImageFont.truetype(regular_path, font_size) if regular_path else ImageFont.load_default()
    except Exception:
        regular_font = ImageFont.load_default()
    try:
        bold_font = ImageFont.truetype(bold_path, font_size) if bold_path else regular_font
    except Exception:
        bold_font = regular_font
    runs = []
    index = 0
    # Handle **bold** with non-greedy match; ignore empty matches
    for match in re.finditer(r'\*\*(.+?)\*\*', text):
        if match.start() > index:
            runs.append((text[index:match.start()], False))
        inner = match.group(1)
        if inner:
            runs.append((inner, True))
        index = match.end()
    if index < len(text):
        runs.append((text[index:], False))
    if not runs:
        runs = [('', False)]
    margin = max(20, border * 2 + 8)
    max_text_width = max(200, width - 2 * margin)
    space_width = regular_font.getbbox(' ')[2] - regular_font.getbbox(' ')[0]

    def _word_width(t):
        f = bold_font if t[1] else regular_font
        b = f.getbbox(t[0])
        return b[2] - b[0]

    # Build words (with their bold flag) preserving ** run boundaries.
    tokens = [
        (w, is_bold)
        for run_text, is_bold in runs
        for w in run_text.split()
        if w
    ]

    # Wrap at WORD boundaries so we never split a word across two lines.
    lines = []  # list of (list[(word, is_bold)], line_width)
    current = []
    current_width = 0
    for tok in tokens:
        ww = _word_width(tok)
        sep = 0 if not current else space_width
        if current and current_width + sep + ww > max_text_width:
            lines.append((current, current_width))
            current = []
            current_width = 0
            sep = 0
        current.append(tok)
        current_width += sep + ww
    if current:
        lines.append((current, current_width))
    if not lines:
        return None
    line_height = font_size + max(8, border * 2)
    # Create full-resolution transparent image so overlay at 0,0 puts caption at bottom
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color_rgba = _CAPTION_COLORS.get(str(color).lower(), _CAPTION_COLORS['white'])
    # Draw from bottom up
    total_text_height = line_height * len(lines)
    y = height - total_text_height - margin
    for line, line_width in lines:
        x = (width - line_width) // 2
        for word, is_bold in line:
            font = bold_font if is_bold else regular_font
            draw.text((x, y), word, font=font, fill=color_rgba, stroke_width=border, stroke_fill=(0, 0, 0, 255))
            x += (font.getbbox(word)[2] - font.getbbox(word)[0]) + space_width
        y += line_height
    working_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'work')
    os.makedirs(working_dir, exist_ok=True)
    path = os.path.join(working_dir, f"caption_{int(time.time() * 1000)}.png")
    img.save(path)
    return path


def build_caption_pngs(segments: List[Dict], width: int, height: int) -> List[Dict]:
    """Segments: list of {text, start, end}. Return list of {path, start, end} overlay images."""
    from .video_settings import CAPTION_FONT, CAPTION_FONT_SIZE, CAPTION_COLOR, CAPTION_BORDER
    font_size = max(16, int(round(int(CAPTION_FONT_SIZE) * height / 1080)))
    border = max(1, int(round(int(CAPTION_BORDER) * height / 1080)))
    regular_path = _font_path_for(CAPTION_FONT, bold=False)
    bold_path = _font_path_for(CAPTION_FONT, bold=True)
    overlays = []
    try:
        for segment in segments or []:
            text = str(segment.get('text') or '').strip()
            start = float(segment.get('start') or 0)
            end = float(segment.get('end') or start)
            if not text or end <= start:
                continue
            path = _render_caption_png(text, font_size, CAPTION_COLOR, border, regular_path, bold_path, width, height)
            if path and os.path.exists(path):
                overlays.append({'path': path, 'start': start, 'end': end})
    except Exception as e:
        # Caption rendering must never fail generation; drop captions, clean partials.
        print(f"Error building caption PNGs, skipping captions: {e}")
        for overlay in overlays:
            try:
                os.remove(overlay['path'])
            except Exception:
                pass
        return []
    return overlays

def generate_thumbnail(video_path, width=1280):
    """Extract a thumbnail from a video, skipping the first 2s (likely black intro)."""
    import subprocess
    if not os.path.exists(video_path):
        return None
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'final')
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(video_path))[0]
    out_path = os.path.join(out_dir, f"{base}_thumb.jpg")
    cmd = ['ffmpeg', '-ss', '2', '-i', video_path, '-frames:v', '1', '-vf', f'scale={width}:-2', '-q:v', '2', '-y', out_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            print(f"Thumbnail created: {out_path}")
            return out_path
        print(f"Thumbnail generation failed: {result.stderr[-300:]}")
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
    return None


class VideoAssemblyService:
    def __init__(self):
        # Use consolidated directories at the project root level
        self.working_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'work')
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'final')
        os.makedirs(self.working_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
    
    def cut_video_segment(self, video_file: str, start_time: float, duration: float, output_filename: str = None) -> Optional[str]:
        """Cut a segment from a video file with proper keyframe alignment"""
        try:
            if not os.path.exists(video_file):
                raise ValueError("Video file not found")
            
            if not output_filename:
                base_name = os.path.splitext(os.path.basename(video_file))[0]
                output_filename = f"{base_name}_cut_{int(time.time())}.mp4"
            
            output_path = os.path.join(self.working_dir, output_filename)
            
            # Build FFmpeg command to cut video segment with proper keyframe alignment
            # Using -ss before -i for faster seeking
            # Adding keyframe alignment to prevent frozen frames
            # Using -avoid_negative_ts and -fflags for proper timestamp handling
            # Adding -vsync for variable frame rate
            cmd = [
                'ffmpeg',
                '-ss', str(start_time),
                '-i', video_file,
                '-t', str(duration),
                '-c', 'copy',  # Use stream copy to preserve original quality and avoid re-encoding
                '-avoid_negative_ts', 'make_zero',
                '-fflags', '+genpts',
                '-fps_mode', 'vfr',  # Variable frame rate to prevent frozen frames
                '-y',  # Overwrite output file
                output_path
            ]
            
            print(f"Cutting video segment: {' '.join(cmd)}")
            
            # Execute FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)  # 2 minute timeout
            
            if result.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"Successfully created video segment at: {output_path} (Size: {file_size} bytes)")
                return output_path
            else:
                print(f"FFmpeg error (return code {result.returncode}): {result.stderr}")
                # If stream copy fails, try re-encoding with better parameters
                cmd = [
                    'ffmpeg',
                    '-ss', str(start_time),
                    '-i', video_file,
                    '-t', str(duration),
                    '-c:v', 'libx264',
                    '-c:a', 'aac',
                    '-strict', 'experimental',
                    '-avoid_negative_ts', 'make_zero',
                    '-fflags', '+genpts',
                    '-fps_mode', 'vfr',  # Variable frame rate to prevent frozen frames
                    '-movflags', '+faststart',  # Optimize for web streaming
                    '-y',  # Overwrite output file
                    output_path
                ]
                print(f"Retrying with re-encoding: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode == 0 and os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    print(f"Successfully created video segment with re-encoding at: {output_path} (Size: {file_size} bytes)")
                    return output_path
                else:
                    print(f"FFmpeg re-encoding error (return code {result.returncode}): {result.stderr}")
                    return None
                
        except subprocess.TimeoutExpired:
            print("FFmpeg process timed out")
            return None
        except Exception as e:
            print(f"Error cutting video segment: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _calculate_optimal_clip_duration(self, target_duration: float) -> float:
        """
        Calculate an optimal clip duration between 3-7 seconds
        """
        # Aim for an average of 5 seconds, but allow variation
        min_duration = 3.0
        max_duration = 7.0
        avg_duration = 5.0
        
        # Adjust based on target duration
        if target_duration < min_duration:
            return target_duration
        elif target_duration > max_duration:
            # For longer segments, we might want to use a portion of it
            return min(target_duration, max_duration)
        else:
            return target_duration
    
    def _distribute_clips_evenly(self, total_duration: float, num_clips: int) -> List[float]:
        """
        Distribute clip durations evenly with 3-4 second average.
        """
        if num_clips <= 0:
            return []
        # Physical limit: 60s / 2.0s min clip = 30 clips. If we hand over many
        # clips the 2.0s floor makes line 326 go NEGATIVE; the buggy result
        # collapses to ~40s output. Trim the clip list to what actually fits at
        # the 2.5s +- floor so the sum stays at total_duration.
        max_fit = int(total_duration // 2.5)
        if num_clips > max_fit:
            num_clips = max_fit
        # Calculate base duration per clip (aim for 3-4 seconds)
        base_duration = total_duration / num_clips
        
        # Adjust to fit within 3-4 second range for better consistency
        if base_duration < 3.0:
            base_duration = 3.0
        elif base_duration > 4.0:
            base_duration = 4.0
            
        # Create durations with minimal variation for consistent pacing
        durations = []
        remaining_time = total_duration
        
        for i in range(num_clips):
            # For the last clip, use exactly the remaining time
            if i == num_clips - 1:
                clip_duration = remaining_time
            else:
                # Use base duration with minimal variation (±0.3 seconds) for 3-4 second clips
                variation = random.uniform(-0.3, 0.3)
                clip_duration = max(2.5, min(4.5, base_duration + variation))
                # Make sure we don't exceed remaining time significantly
                clip_duration = min(clip_duration, remaining_time - (num_clips - i - 1) * 2.0)
            
            durations.append(clip_duration)
            remaining_time -= clip_duration
            
            # Safety check to prevent negative remaining time
            if remaining_time <= 0 and i < num_clips - 1:
                # Redistribute remaining clips with minimum duration
                remaining_clips = num_clips - i - 1
                if remaining_clips > 0:
                    remaining_duration_per_clip = max(2.5, remaining_time / remaining_clips)
                    for j in range(remaining_clips):
                        durations.append(remaining_duration_per_clip)
                break
        
        # Final adjustment to ensure total duration is exactly right
        if durations:
            # Adjust the last clip to make sure we use exactly the total duration
            total_so_far = sum(durations[:-1])
            durations[-1] = total_duration - total_so_far
            
            # Ensure the last clip is within reasonable bounds
            if durations[-1] < 2.0:
                # If last clip is too short, redistribute a bit from previous clips
                adjustment = 2.0 - durations[-1]
                durations[-1] = 2.0
                # Distribute adjustment across previous clips
                if len(durations) > 1:
                    per_clip_adjustment = adjustment / (len(durations) - 1)
                    for i in range(len(durations) - 1):
                        durations[i] -= per_clip_adjustment
        
        return durations
    
    def assemble_video(self, 
                      video_files: List[Tuple[str, float, Dict]], 
                      audio_file: str, 
                      scene_timings: List[Dict],
                      output_filename: str = None,
total_duration: int = 30,
                       orientation: str = "landscape",
                       width: int = 1920,
                       height: int = 1080,
                       niche: Dict = None) -> Optional[str]:
        """
        Assemble video clips with audio using FFmpeg, cutting clips to match scene timings
        
        Args:
            video_files: List of tuples (video_path, duration, metadata)
            audio_file: Path to audio file
            scene_timings: List of scene timing information
            output_filename: Output filename
            total_duration: Total video duration in seconds
        """
        try:
            if not video_files:
                raise ValueError("No video files provided")
            
            if not output_filename:
                output_filename = f"assembled_video_{int(time.time())}.mp4"
            
            output_path = os.path.join(self.output_dir, output_filename)
            print(f"Attempting to assemble video to: {output_path}")
            print(f"Video files: {video_files}")
            print(f"Audio file: {audio_file}")
            print(f"Scene timings: {scene_timings}")
            print(f"Total duration: {total_duration}")
            
            # Normalize video_files format to always have 3 elements
            normalized_video_files = []
            for video_item in video_files:
                if len(video_item) == 2:
                    # Old format: (video_path, duration)
                    video_path, duration = video_item
                    metadata = {}
                    normalized_video_files.append((video_path, duration, metadata))
                elif len(video_item) == 3:
                    # New format: (video_path, duration, metadata)
                    normalized_video_files.append(video_item)
                else:
                    print(f"Warning: Unexpected video item format: {video_item}")
                    continue
            
            # Calculate optimal clip durations (3-6 seconds average)
            # Match the number of clips to the number of available videos
            num_clips = len(normalized_video_files)
            clip_durations = self._distribute_clips_evenly(total_duration, num_clips)
            
            # Ensure we don't try to process more videos than we have durations for
            if len(normalized_video_files) > len(clip_durations):
                normalized_video_files = normalized_video_files[:len(clip_durations)]
            
            # Cut video segments with proper timing
            cut_videos = []
            for i, (video_file, video_duration, metadata) in enumerate(normalized_video_files):
                if i >= len(clip_durations):
                    break
                    
                target_duration = clip_durations[i]
                
                # If video is significantly longer than needed, cut a segment
                if video_duration > target_duration + 0.5:  # Only cut if source is more than 0.5 second longer
                    # Cut from a random position to get varied content
                    # Leave a very small buffer to prevent frozen frames at the end
                    buffer_time = 0.1  # Fixed small buffer to prevent frozen frames
                    max_start_time = max(0, video_duration - target_duration - buffer_time)
                    start_time = random.uniform(0, max_start_time)
                    # Ensure we don't cut too close to the end of the source video
                    cut_duration = min(target_duration, video_duration - start_time - buffer_time)
                    
                    # Ensure minimum clip duration to prevent issues
                    if cut_duration < 0.5:  # Minimum 0.5 second for a meaningful clip
                        cut_duration = min(target_duration, max(0.5, video_duration - buffer_time))
                        start_time = max(0, video_duration - cut_duration - buffer_time)
                    
                    cut_filename = f"cut_segment_{i}_{int(time.time())}.mp4"
                    cut_video = self.cut_video_segment(video_file, start_time, cut_duration, cut_filename)
                    if cut_video and os.path.exists(cut_video):
                        cut_videos.append(cut_video)
                    else:
                        # If cutting fails, try to use a segment from the beginning
                        safe_duration = min(target_duration, max(0.5, video_duration - buffer_time))  # Leave buffer
                        cut_video = self.cut_video_segment(video_file, 0, safe_duration, cut_filename)
                        if cut_video and os.path.exists(cut_video):
                            cut_videos.append(cut_video)
                        else:
                            # If all cutting fails, use original (will be trimmed in final assembly)
                            cut_videos.append(video_file)
                else:
                    # Use the whole video if it's close to or shorter than target duration
                    # But ensure it's at least 0.5 second
                    if video_duration >= 0.5:
                        cut_videos.append(video_file)
                    else:
                        # If video is too short, try to extend by using it as-is (will be padded)
                        cut_videos.append(video_file)
            
            # Build caption segments from scene timings (text = voiceover)
            caption_segments = []
            for scene in scene_timings or []:
                text = str(scene.get('voiceover') or '').strip()
                if not text:
                    continue
                start = max(0.0, float(scene.get('start_time') or 0))
                end = min(float(total_duration), float(scene.get('end_time') or start))
                if end <= start:
                    continue
                caption_segments.append({'text': text, 'start': start, 'end': end})
            
            # Create a temporary file list for FFmpeg
            file_list_path = os.path.join(self.working_dir, f"file_list_{int(time.time())}.txt")
            with open(file_list_path, 'w') as f:
                for video_file in cut_videos:
                    if os.path.exists(video_file):
                        # Properly escape backslashes in Windows paths
                        escaped_path = video_file.replace('\\', '\\\\')
                        f.write(f"file '{escaped_path}'\n")
            print(f"Created file list: {file_list_path}")
            
            # Build FFmpeg command with proper audio selection and timing
            # Use -map to explicitly select the video streams from the concat input and audio from the tts file
            # Add proper resolution and orientation handling
            # Use concat demuxer with proper parameters to prevent frozen frames
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', file_list_path,
                '-i', audio_file,
                '-map', '0:v:0',  # Map video from first input (concatenated videos)
                '-map', '1:a:0',  # Map audio from second input (TTS audio)
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-strict', 'experimental',
                '-avoid_negative_ts', 'make_zero',  # Critical for preventing frozen frames
                '-fflags', '+genpts',  # Generate presentation timestamps
                '-fps_mode', 'vfr',  # Use variable frame rate mode instead of deprecated vsync
                '-shortest',  # Ensure video ends when the shortest stream (audio) ends
                '-async', '1',  # Audio/video sync
            ]
            
            # Use video filter for consistent scaling and cropping
            if orientation == "square" and width == height:
                # For square output, crop landscape videos to center square
                cmd.extend(['-vf', f'crop=min(iw\\,ih):min(iw\\,ih),scale={width}:{height}'])
            else:
                # For other orientations, use video filter scaling instead of -s parameter
                cmd.extend(['-vf', f'scale={width}:{height}'])
                
            cmd.extend([
                '-aspect', f'{width}:{height}',  # Set aspect ratio
                '-t', str(total_duration),  # Set output duration
                '-af', 'apad=pad_dur=0',  # Pad audio if needed to reach full duration
                '-movflags', '+faststart',  # Optimize for web streaming
                '-y',  # Overwrite output file
                output_path
            ])
            print(f"FFmpeg command: {' '.join(cmd)}")
            
            # Execute FFmpeg and wait for completion
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5 minute timeout
            print(f"FFmpeg return code: {result.returncode}")
            print(f"FFmpeg stdout: {result.stdout}")
            print(f"FFmpeg stderr: {result.stderr}")
            
            # Clean up temporary file
            if os.path.exists(file_list_path):
                os.remove(file_list_path)
            
            # Clean up cut video segments
            for cut_video in cut_videos:
                if cut_video != output_path and 'cut_segment' in cut_video:
                    try:
                        os.remove(cut_video)
                    except:
                        pass  # Ignore errors in cleanup

            # Clean up the downloaded source clips. They were only needed to cut
            # segments, which the concat demuxer has already consumed by now. Not
            # removing them lets the work/ dir fill the disk across runs (which
            # manifests as 'Invalid argument' on the caption-burn / final mux
            # when the disk hits 100%).
            for vf, _, _ in normalized_video_files:
                if (vf and vf != output_path and os.path.exists(vf)
                        and 'stock_' in os.path.basename(vf)):
                    try:
                        os.remove(vf)
                    except:
                        pass
            
            # Check if the process completed successfully and file was created
            if result.returncode == 0:
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    print(f"Successfully created video at: {output_path} (Size: {file_size} bytes)")
                    captions = build_caption_pngs(caption_segments, width, height)
                    if captions:
                        self._burn_captions(output_path, captions, total_duration, niche=niche)
                    return output_path
                else:
                    print(f"FFmpeg reported success but output file does not exist: {output_path}")
                    return None
            else:
                print(f"FFmpeg error (return code {result.returncode}): {result.stderr}")
                if os.path.exists(output_path):
                    print(f"Output file exists but may be corrupted")
                else:
                    print(f"Output file was not created")
                return None
                
        except subprocess.TimeoutExpired:
            print("FFmpeg process timed out")
            return None
        except Exception as e:
            print(f"Error assembling video: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _burn_captions(self, video_path: str, captions: List[Dict], total_duration: float, niche: Dict = None) -> str:
        # Word-level transcript ({word,start,end}) routes to the ASS burn path;
        # scene caption PNG dicts ({text,start,end,path}) keep the legacy overlay path.
        if captions and isinstance(captions[0], dict) and 'word' in captions[0]:
            return self._burn_word_captions(video_path, captions, total_duration, niche=niche)
        try:
            temp_path = os.path.join(self.output_dir, f"{os.path.basename(video_path)}.captions_{int(time.time())}.tmp.mp4")
            inputs = ['ffmpeg', '-i', video_path]
            for caption in captions:
                inputs.extend(['-i', caption['path']])
            filter_parts = []
            previous_label = '0:v'
            for index, caption in enumerate(captions):
                label = f'c{index + 1}'
                start = max(0.0, float(caption['start']))
                end = min(float(total_duration), float(caption['end']))
                if end <= start:
                    continue
                filter_parts.append(
                    f"[{previous_label}][{index + 1}:v]overlay=0:0:enable='between(t,{start},{end})'[{label}]"
                )
                previous_label = label
            if not filter_parts:
                return video_path
            cmd = inputs + [
                '-filter_complex', ';'.join(filter_parts),
                '-map', f'[{previous_label}]',
                '-map', '0:a?',
                '-c:v', 'libx264',
                '-c:a', 'copy',
                '-movflags', '+faststart',
                '-y',
                temp_path
            ]
            print(f"Burning captions: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0 and os.path.exists(temp_path):
                os.replace(temp_path, video_path)
                print(f"Captions burned into: {video_path}")
            else:
                print(f"Caption burn failed, keeping plain video: {result.stderr[-300:]}")
            return video_path
        except Exception as e:
            print(f"Error burning captions: {e}")
            return video_path
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            for caption in captions:
                path = caption.get('path')
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass

    def _burn_word_captions(self, video_path: str, transcript: List[Dict], total_duration: float, niche: Dict = None) -> str:
        """Burn word-level captions from an ASS file, writing an .srt sidecar.

        Falls back to the plain video on any failure (libass may be missing from
        the ffmpeg build, mirroring the legacy caption burn's never-fail design).
        """
        ass_path = None
        temp_path = None
        try:
            from src.services.video.captions import build_ass, burn_ass, export_srt
            ass_path = os.path.join(self.working_dir, f"word_captions_{int(time.time())}.ass")
            with open(ass_path, 'w', encoding='utf-8') as f:
                f.write(build_ass(transcript, niche))
            srt_path = os.path.splitext(video_path)[0] + '.srt'
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(export_srt(transcript))
            temp_path = os.path.join(self.output_dir, f"{os.path.basename(video_path)}.wordcaps_{int(time.time())}.tmp.mp4")
            burn_ass(video_path, ass_path, temp_path)
            if os.path.exists(temp_path):
                os.replace(temp_path, video_path)
                print(f"Word captions burned into: {video_path}")
            return video_path
        except Exception as e:
            print(f"Word caption burn failed, keeping plain video: {e}")
            return video_path
        finally:
            for path in (ass_path, temp_path):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass

    def add_subtitles(self, 
                     video_file: str, 
                     subtitle_text: str, 
                     output_filename: str = None) -> Optional[str]:
        """Add subtitles to video using FFmpeg"""
        try:
            if not os.path.exists(video_file):
                raise ValueError("Video file not found")
            
            if not output_filename:
                base_name = os.path.splitext(os.path.basename(video_file))[0]
                output_filename = f"{base_name}_subtitled_{int(time.time())}.mp4"
            
            output_path = os.path.join(self.output_dir, output_filename)
            
            # Create temporary subtitle file
            subtitle_path = os.path.join(self.working_dir, f"subtitles_{int(time.time())}.srt")
            self._create_srt_file(subtitle_text, subtitle_path)
            
            # Build FFmpeg command for subtitles
            cmd = [
                'ffmpeg',
                '-i', video_file,
                '-vf', f"subtitles={subtitle_path}",
                '-c:a', 'copy',
                '-y',  # Overwrite output file
                output_path
            ]
            
            # Execute FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Clean up temporary files
            if os.path.exists(subtitle_path):
                os.remove(subtitle_path)
            
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
            else:
                print(f"FFmpeg subtitle error: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"Error adding subtitles: {e}")
            return None
    
    def _create_srt_file(self, text: str, filepath: str):
        """Create a simple SRT subtitle file"""
        # This is a very basic subtitle generation
        # In practice, you'd want to parse the script and create timed subtitles
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("1\n")
            f.write("00:00:00,000 --> 00:00:30,000\n")
            f.write(text[:100] + "...\n")  # First 100 characters as subtitle
            f.write("\n")

# Global instance
assembly_service = VideoAssemblyService()