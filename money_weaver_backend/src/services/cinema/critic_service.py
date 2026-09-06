from __future__ import annotations

import os
import subprocess


def build_storyboard(shots, resolve, out_dir: str, image_size: int = 320) -> list[dict]:
    """Extract the middle frame of each shot's SEGMENT via ffmpeg. TimelineShot
    in/out points are TIMELINE positions, not clip-local: the rendered segment
    for shot i is [in_point_s, out_point_s) of the assembled timeline, which
    corresponds to clip-local [0, out-in) of the cut clip (assembly cuts each
    clip to exactly its shot duration). So the storyboard frame is extracted at
    clip-local (out-in)/2 of the resolved clip file.

    shot_index is the POSITION in plan.shots (enumerate) — skips must not shift
    alignment between frames and specs. Never raises; returns what succeeded."""
    rows: list[dict] = []
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        return []
    for i, shot in enumerate(shots):
        try:
            path = resolve(shot.clip_id)
            if not path or not os.path.exists(path):
                continue
            dur = max(0.1, (shot.out_point_s or 2.5) - (shot.in_point_s or 0.0))
            mid = round(dur / 2.0, 3)  # clip-local middle of the rendered segment
            frame_path = os.path.join(out_dir, f"shot_{i:02d}.jpg")
            r = subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(mid), "-i", path,
                 "-frames:v", "1", "-vf", f"scale={image_size}:-1", frame_path],
                timeout=60, check=False)
            if r.returncode == 0 and os.path.exists(frame_path):
                rows.append({"shot_index": i,
                             "clip_id": shot.clip_id, "frame_path": frame_path})
        except Exception:
            continue
    return rows
