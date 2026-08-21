"""Smart 9:16 reframe service — port of openshorts reframe_v2.

GENERAL mode composites the input onto a blurred 1080x1920 background in a
single ffmpeg pass (subprocess.run, check=True). TRACK mode (YOLOv8 person
tracking + MediaPipe face-center crop) is stubbed: it lazily imports the heavy
ML deps and degrades to GENERAL when they are missing — and for now even when
present, until the full openshorts TRACK port lands.
"""

import os
import subprocess
import uuid

TARGET_W = 1080
TARGET_H = 1920

# Outputs land in the served backend/final dir (same location sibling tasks
# publish through), not a per-call mkdtemp that would accumulate forever.
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    'final',
)

# Blur-background composite filtergraph:
#   bg: scale to fill 1080x1920, crop to frame, boxblur
#   fg: scale to fit inside 1080x1920 (aspect preserved)
#   overlay fg centered on bg -> [out]
_VF_BLUR_BG = (
    "split[bg][fg];"
    f"[bg]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
    f"crop={TARGET_W}:{TARGET_H},boxblur=20:5[bgb];"
    f"[fg]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease[fgs];"
    "[bgb][fgs]overlay=(W-w)/2:(H-h)/2[out]"
)


def _output_path(input_mp4):
    base = os.path.splitext(os.path.basename(input_mp4))[0]
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return os.path.join(OUTPUT_DIR, f"{base}_{uuid.uuid4().hex[:8]}_9x16.mp4")


def _reframe_general(input_mp4):
    out = _output_path(input_mp4)
    cmd = [
        "ffmpeg", "-y",
        "-i", input_mp4,
        "-filter_complex", _VF_BLUR_BG,
        "-map", "[out]",
        "-map", "0:a?",
        "-c:a", "copy",
        out,
    ]
    subprocess.run(cmd, check=True)
    return out


def reframe(input_mp4, mode="general"):
    """Reframe input_mp4 as vertical 1080x1920; returns the output .mp4 path.

    mode="general": ffmpeg blur-background composite (always available).
    mode="track":   smart subject tracking; falls back to GENERAL when
                    ultralytics/mediapipe are not installed.
    """
    if mode not in ("general", "track"):
        raise ValueError(f"unknown reframe mode: {mode!r}")
    if mode == "track":
        try:
            from ultralytics import YOLO  # noqa: F401
            import mediapipe  # noqa: F401

            # TODO(port): full openshorts reframe_v2 TRACK logic — YOLOv8
            # person tracking + MediaPipe face-center crop across frame
            # windows. Until ported, TRACK intentionally degrades to GENERAL.
            return _reframe_general(input_mp4)
        except ImportError:
            return _reframe_general(input_mp4)
    return _reframe_general(input_mp4)
