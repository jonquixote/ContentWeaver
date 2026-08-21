"""Viral moment detection — port of openshorts viral pipeline.

Pipeline: faster_whisper word-level transcript + scenedetect cuts -> Gemini
prompt asking for 3-15 viral 15-60s moments with hooks. Every stage is a lazy
import so the module works in venvs without the heavy deps, and
detect_viral_moments NEVER raises to the caller: on any failure it degrades to
raw scene cuts, then to [].
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


def transcribe(path):
    """Word-level transcript via faster_whisper.

    Returns [{word, start, end}, ...]. Lazy import: raises ImportError when
    faster_whisper is not installed (caller falls back).
    """
    from faster_whisper import WhisperModel

    model = WhisperModel("small")
    segments, _ = model.transcribe(path, word_timestamps=True)
    return [
        {"word": w.word, "start": w.start, "end": w.end}
        for s in segments
        for w in (s.words or [])
    ]


# Indirection points so tests can patch scenedetect classes without
# sys.modules hacks.
def _VideoManager(*args, **kwargs):
    from scenedetect import VideoManager
    return VideoManager(*args, **kwargs)


def _SceneManager(*args, **kwargs):
    from scenedetect import SceneManager
    return SceneManager(*args, **kwargs)


def detect_scenes(path):
    """Scene cut boundaries [(start_sec, end_sec), ...] via PySceneDetect
    ContentDetector (BSD-3). Returns [] on missing dep or unreadable file."""
    try:
        from scenedetect import ContentDetector
    except ImportError:
        return []
    try:
        vm = _VideoManager([path])
        sm = _SceneManager()
        sm.add_detector(ContentDetector(threshold=27.0))
        vm.set_downscale_factor()
        vm.start()
        sm.detect_scenes(frame_source=vm)
        scene_list = sm.get_scene_list()
    except Exception:
        return []
    cuts = [(start.get_seconds(), end.get_seconds()) for start, end in scene_list]
    return _merge_short_scenes(cuts, min_len=1.0)


def _merge_short_scenes(scenes, min_len=1.0):
    """Merge scenes shorter than min_len into their neighbor (openshorts
    scene_worker behavior). A leading fragment merges forward."""
    if not scenes:
        return []
    merged = []
    for start, end in scenes:
        if merged and (end - start) < min_len:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    if len(merged) > 1 and (merged[0][1] - merged[0][0]) < min_len:
        merged[1][0] = merged[0][0]
        merged.pop(0)
    return [(s, e) for s, e in merged]


def call_gemini(transcript, scenes):
    """Ask Gemini for 3-15 viral 15-60s moments with hooks.

    Returns [{"start", "end", "score", "hook"}, ...]. Raises RuntimeError when
    GEMINI_API_KEY is absent so detect_viral_moments falls back to scene cuts.
    """
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY not set; viral detection unavailable')

    from google import genai

    client = genai.Client(api_key=api_key)
    prompt = (
        "You are a short-form video editor. Given the transcript and scene "
        "cuts below, detect 3-15 viral moments of 15-60 seconds each. Each "
        "moment must open with a strong hook. Respond ONLY with a JSON array "
        'of objects: [{"start": <sec>, "end": <sec>, "score": <0-1>, '
        '"hook": "<one-line hook>"}].\n\n'
        f"Transcript words: {transcript}\n\nScene cuts: {scenes}"
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    text = (response.text or "").strip()
    # Non-greedy extraction: decode the FIRST complete JSON array instead of
    # regex-greedy matching, which can swallow prose between two arrays.
    decoder = json.JSONDecoder()
    moments = None
    for idx, char in enumerate(text):
        if char != "[":
            continue
        try:
            moments, _ = decoder.raw_decode(text[idx:])
            break
        except json.JSONDecodeError:
            continue
    if not isinstance(moments, list):
        raise RuntimeError(f"Gemini returned no JSON array: {text[:200]}")
    return [
        {
            "start": float(m["start"]),
            "end": float(m["end"]),
            "score": float(m.get("score", 0.0)),
            "hook": str(m.get("hook", "")),
        }
        for m in moments
    ]


def _scene_cut_fallback(scenes, count):
    """Shape raw scene cuts as score-less clips."""
    return [
        {"start": float(a), "end": float(b), "score": 0.0, "hook": ""}
        for a, b in list(scenes)[:count]
    ]


def detect_viral_moments(video_path, count=5):
    """Detect the top `count` viral moments in video_path.

    Returns a list of {start, end, score, hook} dicts. Never raises: on any
    failure (missing key, missing dep, API error) it degrades to scene cuts,
    then to [].
    """
    # Detect scene cuts once, up front, so the fallback path reuses them
    # instead of re-running detection after a Gemini failure.
    try:
        scenes = detect_scenes(video_path)
    except Exception:  # noqa: BLE001 - deliberate catch-all fallback
        scenes = []
    try:
        transcript = transcribe(video_path)
        moments = call_gemini(transcript, scenes)
        if moments:
            return moments[:count]
        raise RuntimeError("Gemini returned no viral moments")
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all fallback
        logger.warning(
            "viral detection degraded (%s); falling back to scene cuts", exc)
        return _scene_cut_fallback(scenes, count)
