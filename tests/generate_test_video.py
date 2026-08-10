#!/usr/bin/env python3
"""
Generate a simple test video file for testing the video player using ffmpeg.
"""

import subprocess
import os

def create_test_video_with_ffmpeg(output_path):
    """
    Create a simple test video using ffmpeg.
    
    Args:
        output_path (str): Path where the video will be saved
    """
    # Check if ffmpeg is available
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ffmpeg is not installed or not available in PATH")
        print("Please install ffmpeg to generate test videos")
        return False
    
    # Create a simple test video with color bars and text
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output file
        '-f', 'lavfi',  # Use lavfi input format
        '-i', 'testsrc2=duration=10:size=640x480:rate=30',  # Generate test pattern
        '-vf', 'hue=s=0',  # Desaturate to make it grayscale
        '-vcodec', 'libx264',  # Use H.264 codec
        '-preset', 'ultrafast',  # Fast encoding
        '-tune', 'zerolatency',  # Low latency
        '-pix_fmt', 'yuv420p',  # Pixel format
        '-t', '10',  # Duration in seconds
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Test video created successfully: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error creating video: {e}")
        print(f"stderr: {e.stderr}")
        return False

def create_simple_test_video_with_ffmpeg(output_path):
    """
    Create a very simple test video for quick testing.
    """
    # Check if ffmpeg is available
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ffmpeg is not installed or not available in PATH")
        print("Please install ffmpeg to generate test videos")
        return False
    
    # Create a simple color video
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output file
        '-f', 'lavfi',  # Use lavfi input format
        '-i', 'color=c=blue:s=640x480:d=5:r=30',  # Blue background for 5 seconds
        '-vf', 'drawtext=fontfile=/System/Library/Fonts/Arial.ttf:text=\'MoneyWeaver Test Video\':fontcolor=white:fontsize=24:x=(w-text_w)/2:y=(h-text_h)/2',  # Add text
        '-vcodec', 'libx264',  # Use H.264 codec
        '-preset', 'ultrafast',  # Fast encoding
        '-pix_fmt', 'yuv420p',  # Pixel format
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Simple test video created successfully: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error creating video: {e}")
        print(f"stderr: {e.stderr}")
        return False

if __name__ == "__main__":
    # Create the test video in the public/final directory
    output_path = "/Users/johnny/Downloads/MoneyWeaver/money_weaver_frontend/public/final/project_17_assembler.mp4"
    
    print("Creating test video with ffmpeg...")
    if create_simple_test_video_with_ffmpeg(output_path):
        print("Test video generation complete!")
    else:
        print("Failed to create test video. Trying alternative method...")
        
        # Try to create an empty file as a placeholder
        try:
            with open(output_path, 'w') as f:
                f.write("")
            print(f"Created empty placeholder file: {output_path}")
            print("Note: This won't play as a video, but it will exist at the URL")
        except Exception as e:
            print(f"Failed to create placeholder file: {e}")