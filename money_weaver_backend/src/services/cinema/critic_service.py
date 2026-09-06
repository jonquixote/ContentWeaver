from __future__ import annotations

import base64 as _b64
import json as _json
import os
import re
import subprocess

import requests

from src.services.cinema.critique_schema import RenderCritique


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


def build_critic_prompt(specs, n_frames: int, agentic: bool = False) -> str:
    """Prompt text for the one-call critic. Static mode: N storyboard frames +
    the ShotSpec list. Agentic mode: whole-video input, timestamped critique."""
    lines = [
        "You are a film-editing critic reviewing a rendered short against its shot plan.",
        "For EACH shot, verdict match/mismatch vs its spec (subject, scale, mood, function).",
        "Flag off-theme picks, near-duplicates the hash missed, and montage-level issues "
        "(scale monotony, missing establishing shot, abrupt joins).",
        'Reply ONLY JSON: {"shots": [{"shot_index": 0, "verdict": "match", "reason": "..."}], '
        '"overall_verdict": "pass", "summary": "..."}. '
        'overall_verdict is "review" if any shot mismatches.',
    ]
    if agentic:
        lines.append("This is whole-video input: include timestamped observations (mm:ss) for each issue.")
    else:
        lines.append(f"You are given {n_frames} storyboard frames in order.")
    for s in specs:
        lines.append(
            f"Shot {s.shot_index} (scene {s.scene_number}, {s.function.value}, {s.scale.value}, "
            f"{s.move.value}, mood {s.mood}): subject={s.subject_concrete} | beats={s.narrative_beats}")
    return "\n".join(lines)


def _gemini_keys() -> list[str]:
    primary = os.getenv("GEMINI_API_KEY") or ""
    fallbacks = [k.strip() for k in (os.getenv("GEMINI_API_KEY_FALLBACKS") or "").split(",") if k.strip()]
    keys = list(dict.fromkeys([primary] + fallbacks))
    return [k for k in keys if k]


def parse_critique(raw: str | None) -> RenderCritique | None:
    """Strict-parse model output. None on ANY failure — the critic is silently
    off for that render (logged by the caller)."""
    if not raw:
        return None
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        data = _json.loads(m.group(0))
        return RenderCritique(**data)
    except Exception:
        return None


class GeminiCriticClient:
    """One POST per render. Model + agentic/static knob from env. Key rotation:
    429 → next key; non-429 failure → bail (None); all keys exhausted → None."""

    def __init__(self, model: str | None = None, timeout_s: int = 60):
        self.model = model or os.getenv("CRITIC_MODEL", "gemini-2.0-flash")
        self.timeout_s = int(os.getenv("CRITIC_TIMEOUT_S", str(timeout_s)))

    def critique(self, frames: list[dict], prompt: str, *,
                 agentic: bool = False, video_path: str | None = None) -> RenderCritique | None:
        keys = _gemini_keys()
        if not keys:
            return None
        parts: list[dict] = [{"text": prompt}]
        if agentic and video_path:
            parts.append({"inline_data": {"mime_type": "video/mp4", "data": _read_b64(video_path)}})
        else:
            for row in frames:
                try:
                    parts.append({"inline_data": {"mime_type": "image/jpeg",
                                                 "data": _read_b64(row["frame_path"])}})
                except Exception:
                    continue
        payload: dict = {"contents": [{"parts": parts}],
                         "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.1}}
        if agentic:
            payload["generationConfig"]["media_processing"] = "AGENTIC"
        raw = None
        for key in keys:
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                    params={"key": key}, json=payload, timeout=self.timeout_s)
            except Exception:
                continue
            if r.status_code == 200:
                try:
                    raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                except Exception:
                    raw = None
                break
            if r.status_code != 429:
                return None  # non-quota failure: bail, don't burn other keys
        return parse_critique(raw)


def _read_b64(path: str) -> str:
    with open(path, "rb") as f:
        return _b64.b64encode(f.read()).decode()


def critique_plan_for_render(timing_plan, clip_durations: list[float]):
    """Single source of truth for the plan the critic scores: reuse the timing
    plan when present, else synthesize a minimal TimelinePlan wrapper from clip
    durations (wrapper, not a bare list, so run_critique's plan.shots works in
    both paths)."""
    if timing_plan is not None:
        return timing_plan
    from src.services.cinema.montage_service import TimelinePlan, TimelineShot
    from src.services.cinema.types import MontageMode
    return TimelinePlan(mode=MontageMode.OVERTONAL, shots=[
        TimelineShot(clip_id=f"clip_{i}", in_point_s=0.0, out_point_s=float(d))
        for i, d in enumerate(clip_durations)])


def maybe_critique_render(plan, specs, resolve, project_id: str, render_id: str,
                          video_path: str | None = None):
    """Flag-gated call-site wrapper. Returns the critique or None. Never raises."""
    import os
    if os.getenv("CINEMA_CRITIC_ENABLED", "false").lower() != "true":
        return None
    try:
        return run_critique(plan, specs, resolve, project_id=project_id,
                            render_id=render_id, video_path=video_path)
    except Exception as e:
        print(f"cinema critic call-site failed, render proceeds: {e}")
        return None


def run_critique(plan, specs, resolve, *, project_id: str, render_id: str,
                 persist_dir: str | None = None, agentic: bool | None = None,
                 video_path: str | None = None) -> RenderCritique | None:
    """Advisory-only v1 entry point. CINEMA_CRITIC_ENABLED=false (or any failure) →
    None. On success persists the critique JSON and returns it. Never raises.
    Agentic + video_path: the video carries the visuals, storyboard skipped."""
    try:
        if os.getenv("CINEMA_CRITIC_ENABLED", "false").lower() != "true":
            return None
        use_agentic = agentic if agentic is not None else (
            os.getenv("CRITIC_MODE", "static").lower() == "agentic")
        if use_agentic and video_path:
            frames: list[dict] = []
        else:
            size = int(os.getenv("CRITIC_IMAGE_SIZE", "320"))
            max_frames = int(os.getenv("CRITIC_MAX_FRAMES", "12"))
            frames = build_storyboard(plan.shots[:max_frames], resolve,
                                      os.path.join(persist_dir or os.getenv("CRITIC_DIR", "/tmp/cw-critic"), "sb"),
                                      image_size=size)
        prompt = build_critic_prompt(specs, n_frames=len(frames), agentic=use_agentic)
        client = GeminiCriticClient()
        critique = client.critique(frames, prompt, agentic=use_agentic, video_path=video_path)
        if critique is None:
            print("cinema critic: skipped (no result)")
            return None
        out_dir = persist_dir or os.getenv("CRITIC_DIR", "/tmp/cw-critic")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, f"{project_id}_{render_id}.json"), "w") as f:
            f.write(critique.model_dump_json())
        print(f"cinema critic: {critique.overall_verdict} ({len(critique.shots)} shots)")
        return critique
    except Exception as e:
        print(f"cinema critic failed, render proceeds: {e}")
        return None
