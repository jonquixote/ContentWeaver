import sys
import os
sys.path.append('/Users/johnny/Downloads/MoneyWeaver/money_weaver_backend/src')

from services.video.assembly_service import assembly_service

# Test the assembly service
print("Testing assembly service...")

# Get some sample videos with metadata
sample_videos = [
    ("/Users/johnny/Downloads/MoneyWeaver/money_weaver_backend/src/work/sample1.mp4", 5.0, {
        "description": "sample video 1",
        "source": "local",
        "actual_duration": 5.0,
        "width": 1280,
        "height": 720
    }),
    ("/Users/johnny/Downloads/MoneyWeaver/money_weaver_backend/src/work/sample2.mp4", 5.0, {
        "description": "sample video 2",
        "source": "local",
        "actual_duration": 5.0,
        "width": 1280,
        "height": 720
    })
]

# Create a simple audio file for testing (using one of the existing TTS files)
audio_file = "/Users/johnny/Downloads/MoneyWeaver/money_weaver_backend/src/work/script_tts_1756844327.mp3"

print(f"Sample videos: {sample_videos}")
print(f"Audio file: {audio_file}")

# Check if files exist
for video_path, duration, metadata in sample_videos:
    if os.path.exists(video_path):
        print(f"✓ Video exists: {video_path}")
    else:
        print(f"✗ Video does not exist: {video_path}")

if os.path.exists(audio_file):
    print(f"✓ Audio exists: {audio_file}")
else:
    print(f"✗ Audio does not exist: {audio_file}")

# Try to assemble a video
print("\nAssembling video...")
# Create scene timings for testing
scene_timings = [
    {"duration": 15.0, "content": "Scene 1"},
    {"duration": 15.0, "content": "Scene 2"}
]

output_filename = "test_assembled_video.mp4"
final_video_path = assembly_service.assemble_video(
    video_files=sample_videos,
    audio_file=audio_file,
    scene_timings=scene_timings,
    output_filename=output_filename,
    total_duration=30
)

if final_video_path:
    print(f"✓ Successfully created video: {final_video_path}")
    if os.path.exists(final_video_path):
        size = os.path.getsize(final_video_path)
        print(f"  File size: {size} bytes")
    else:
        print("  ⚠ File path returned but file does not exist!")
else:
    print("✗ Failed to create video")