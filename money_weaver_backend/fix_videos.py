#!/usr/bin/env python3
"""
Video Fix Script for MoneyWeaver

This script fixes video files with timestamp issues that prevent them from playing
in HTML5 video players. It identifies problematic videos and re-encodes them to
ensure proper timestamp continuity.

Usage:
    python fix_videos.py [video_path] [--dry-run]

Arguments:
    video_path    Path to a specific video file to fix (optional)
    --dry-run     Show what would be fixed without actually doing it

Examples:
    python fix_videos.py                           # Fix all videos with issues
    python fix_videos.py final/project_16.mp4      # Fix a specific video
    python fix_videos.py --dry-run                 # Show what would be fixed
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def check_video_with_ffmpeg(video_path):
    """Check if a video has errors using ffmpeg"""
    try:
        # Run ffmpeg to check for errors
        result = subprocess.run([
            'ffmpeg', '-v', 'error', '-i', str(video_path), 
            '-f', 'null', '-'
        ], capture_output=True, text=True, timeout=30)
        
        # If there's stderr output, there might be errors
        has_errors = bool(result.stderr.strip())
        return has_errors, result.stderr
    except subprocess.TimeoutExpired:
        return True, "Timeout checking video"
    except Exception as e:
        return True, f"Error checking video: {str(e)}"

def fix_video_timestamps(input_path, output_path=None):
    """Fix video timestamps using ffmpeg"""
    if output_path is None:
        output_path = input_path.with_suffix(input_path.suffix + '.fixed')
    
    try:
        # Re-encode the video with fixed timestamps
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-c:v', 'libx264', '-c:a', 'aac', '-strict', 'experimental',
            '-preset', 'fast', '-y', str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            return True, f"Successfully fixed {input_path.name}"
        else:
            return False, f"Error fixing {input_path.name}: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, f"Timeout fixing {input_path.name}"
    except Exception as e:
        return False, f"Error fixing {input_path.name}: {str(e)}"

def fix_video_copy_method(input_path, output_path=None):
    """Fix video timestamps using copy method (faster)"""
    if output_path is None:
        output_path = input_path.with_suffix(input_path.suffix + '.fixed')
    
    try:
        # Try to fix timestamps with copy method first (faster)
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-c', 'copy', '-avoid_negative_ts', 'make_zero',
            '-fflags', '+genpts', '-y', str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            return True, f"Successfully fixed {input_path.name} (copy method)"
        else:
            return False, f"Copy method failed for {input_path.name}: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, f"Timeout fixing {input_path.name} with copy method"
    except Exception as e:
        return False, f"Error fixing {input_path.name} with copy method: {str(e)}"

def find_problematic_videos(directory):
    """Find all videos with timestamp issues in the directory"""
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv']
    problematic_videos = []
    
    for file_path in Path(directory).rglob('*'):
        if file_path.suffix.lower() in video_extensions:
            has_errors, error_output = check_video_with_ffmpeg(file_path)
            if has_errors and ('non monotonically increasing dts' in error_output or 
                              'Application provided invalid' in error_output):
                problematic_videos.append(file_path)
    
    return problematic_videos

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('video_path', nargs='?', help='Path to a specific video file to fix (optional)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed without actually doing it')
    parser.add_argument('--directory', default='final', help='Directory to search for videos (default: final)')
    
    args = parser.parse_args()
    
    # Check if ffmpeg is available
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ffmpeg is not installed or not available in PATH")
        print("Please install ffmpeg to use this script.")
        sys.exit(1)
    
    if args.video_path:
        # Fix a specific video
        video_path = Path(args.video_path)
        if not video_path.exists():
            print(f"Error: Video file {video_path} does not exist")
            sys.exit(1)
        
        if args.dry_run:
            has_errors, error_output = check_video_with_ffmpeg(video_path)
            if has_errors:
                print(f"Would fix: {video_path}")
                print(f"Errors found: {error_output[:200]}...")
            else:
                print(f"No issues found in {video_path}")
        else:
            print(f"Fixing {video_path}...")
            # Try copy method first (faster)
            success, message = fix_video_copy_method(video_path)
            if not success:
                print(f"  {message}")
                print("  Trying re-encode method...")
                success, message = fix_video_timestamps(video_path)
            
            if success:
                # Replace the original file with the fixed one
                fixed_path = video_path.with_suffix(video_path.suffix + '.fixed')
                if fixed_path.exists():
                    video_path.replace(video_path.with_suffix(video_path.suffix + '.backup'))
                    fixed_path.replace(video_path)
                    print(f"  Successfully fixed {video_path.name}")
                else:
                    print(f"  Warning: Fixed file not found at {fixed_path}")
            else:
                print(f"  Failed to fix {video_path.name}: {message}")
    else:
        # Find and fix all problematic videos
        print(f"Searching for videos with timestamp issues in {args.directory}...")
        problematic_videos = find_problematic_videos(args.directory)
        
        if not problematic_videos:
            print("No videos with timestamp issues found.")
            return
        
        print(f"Found {len(problematic_videos)} videos with timestamp issues:")
        for video in problematic_videos:
            print(f"  - {video}")
        
        if args.dry_run:
            print("\nDry run completed. Use without --dry-run to actually fix the videos.")
            return
        
        # Fix all problematic videos
        print("\nFixing videos...")
        for video_path in problematic_videos:
            print(f"  Fixing {video_path.name}...")
            # Try copy method first (faster)
            success, message = fix_video_copy_method(video_path)
            if not success:
                print(f"    {message}")
                print("    Trying re-encode method...")
                success, message = fix_video_timestamps(video_path)
            
            if success:
                # Replace the original file with the fixed one
                fixed_path = video_path.with_suffix(video_path.suffix + '.fixed')
                if fixed_path.exists():
                    video_path.replace(video_path.with_suffix(video_path.suffix + '.backup'))
                    fixed_path.replace(video_path)
                    print(f"    Successfully fixed {video_path.name}")
                else:
                    print(f"    Warning: Fixed file not found at {fixed_path}")
            else:
                print(f"    Failed to fix {video_path.name}: {message}")

if __name__ == '__main__':
    main()