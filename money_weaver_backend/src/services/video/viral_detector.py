"""Viral moment detection — port of openshorts viral pipeline.

Pipeline: faster_whisper word-level transcript + scenedetect cuts -> Gemini
prompt asking for 3-15 viral 15-60s moments with hooks. Every stage is a lazy
import so the module works in venvs without the heavy deps, and
detect_viral_moments NEVER raises to the caller: on any failure it degrades to
raw scene cuts, then to [].
"""

import os


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


def detect_scenes(path):
    """Scene cut boundaries via scenedetect.

    Returns [(start_sec, end_sec), ...]. STUB for now (mirrors the openshorts
    port state): the scenedetect import is exercised lazily but the analysis
    pass is not wired up yet, so this always returns [] until the full port
    lands.
    """
    try:
        from scenedetect import ContentDetector, SceneManager, VideoManager  # noqa: F401
    except ImportError:
        return []
    # TODO(port): run VideoManager/SceneManager with ContentDetector and
    # return the cut list like openshorts scene_worker.
    return []


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
    import json
    import re

    text = (response.text or "").strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise RuntimeError(f"Gemini returned no JSON array: {text[:200]}")
    moments = json.loads(match.group(0))
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
    try:
        transcript = transcribe(video_path)
        scenes = detect_scenes(video_path)
        moments = call_gemini(transcript, scenes)
        if moments:
            return moments[:count]
        raise RuntimeError("Gemini returned no viral moments")
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all fallback
        print(f"viral detection degraded ({exc}); falling back to scene cuts")
        try:
            return _scene_cut_fallback(detect_scenes(video_path), count)
        except Exception:  # noqa: BLE001
            return []
