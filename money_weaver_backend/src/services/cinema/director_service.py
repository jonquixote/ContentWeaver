from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3

from src.services.cinema.cache import cache_dir
from src.services.cinema.shot import ShotSpec
from src.services.cinema.types import CameraMove, ShotFunction, ShotScale


class DirectorError(Exception):
    pass


CONCRETE_RULES = (
    "Rewrite every abstract concept into concrete, filmable imagery. "
    "Never use abstract nouns like 'wealth', 'freedom', 'success', 'fear', 'love'. "
    "Instead say exactly what the camera sees: 'hands counting cash', 'a door "
    "opening to light', 'a crowd cheering', 'a child clutching a broken toy'. "
    "The subject MUST be a concrete noun phrase the camera can photograph."
)

SCALE_HINT = (
    "Shot scale: ecu (extreme close-up), cu (close-up), mcu (medium close-up), "
    "ms (medium shot), mls (medium long shot), ls (long shot), els (extreme long "
    "shot), abstract (no real subject)."
)

MOVE_HINT = (
    "Camera move: static, pan, tilt, dolly_in, dolly_out, track, handheld, "
    "drone, crane, zoom."
)

FUNCTION_HINT = (
    "Shot function: establish, context, detail, reaction, symbol, transition, payoff."
)

DIRECTOR_SCHEMA = (
    'Return ONLY JSON: {"shots": [{"shot_index": 0, "narrative_beats": "string", '
    '"subject_concrete": "string", "scale": "ms", "move": "static", '
    '"function": "establish", "mood": "dim", "screen_direction": "neutral", '
    '"intensity": 0.5, "target_duration_s": 2.5}]}.'
)


def build_director_prompt(scene_text: str, story_context: str) -> str:
    return (
        "You are a film director storyboarding a stock-footage short. Convert one "
        "script scene into an ordered list of shots.\n"
        f"STORY CONTEXT: {story_context}\n"
        f"SCENE: {scene_text}\n"
        f"{CONCRETE_RULES}\n{SCALE_HINT}\n{MOVE_HINT}\n{FUNCTION_HINT}\n"
        f"{DIRECTOR_SCHEMA}"
    )


def parse_director_json(raw: str | None) -> list[ShotSpec] | None:
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except (json.JSONDecodeError, TypeError):
        return None
    shots = data.get("shots") if isinstance(data, dict) else None
    if not isinstance(shots, list) or not shots:
        return []
    out = []
    for s in shots:
        try:
            out.append(
                ShotSpec(
                    scene_number=s.get("scene_number", 0),
                    shot_index=s.get("shot_index", 0),
                    narrative_beats=s.get("narrative_beats", ""),
                    subject_concrete=s.get("subject_concrete", ""),
                    scale=ShotScale(s.get("scale", "ms")),
                    move=CameraMove(s.get("move", "static")),
                    function=ShotFunction(s.get("function", "context")),
                    mood=s.get("mood", ""),
                    screen_direction=s.get("screen_direction", "neutral"),
                    intensity=float(s.get("intensity", 0.5)),
                    target_duration_s=float(s.get("target_duration_s", 2.5)),
                )
            )
        except (ValueError, TypeError):
            continue
    return out


_KEYWORD_SCALE = [
    (("close-up", "face ", "eye", "hand", "mouth", "macro"), ShotScale.CU),
    (("mid", "medium shot", "person", "man", "woman", "people"), ShotScale.MS),
    (("crowd", "audience", "room", "interior", "stage"), ShotScale.MS),
    (("city", "skyline", "landscape", "mountain", "building", "street"), ShotScale.LS),
    (("wide", "establish", "aerial", "drone", "horizon"), ShotScale.ELS),
]


def keyword_to_scale(keyword: str) -> ShotScale:
    k = keyword.lower()
    for keys, scale in _KEYWORD_SCALE:
        if any(t in k for t in keys):
            return scale
    return ShotScale.MS


_DETERMINISTIC_ABSTRACT_MAP = {
    "wealth": "hands counting a stack of cash",
    "freedom": "a door opening to blinding light",
    "success": "a crowd cheering under lights",
    "fear": "a person clutching a broken object",
    "love": "two people embracing in warm light",
    "power": "a fist slamming a desk",
    "despair": "an empty room with a broken mic stand",
}

# Bump when the director's prompt/logic changes so stale cached ShotSpecs are
# never reused. Salted into the cache key.
DIRECTOR_VERSION = "a1"


def _cache_key(scene_text: str) -> str:
    return hashlib.sha256(f"{DIRECTOR_VERSION}:{scene_text}".encode()).hexdigest()


def _concretize(text: str) -> str:
    low = text.lower()
    for abstract, concrete in _DETERMINISTIC_ABSTRACT_MAP.items():
        if abstract in low:
            return concrete
    return text


def deterministic_director(
    scene_text: str, scene_number: int, shot_count_hint: int = 3
) -> list[ShotSpec]:
    """Pure deterministic director: no network, always returns >=1 shot.

    Uses keyword->scale mapping, MS/static default, ESTABLISH first / PAYOFF
    last, fixed pacing. The concrete-subject rule is enforced by mapping known
    abstract nouns to filmable imagery.
    """
    concrete = _concretize(scene_text)
    count = max(1, min(shot_count_hint, 4))
    specs = []
    for i in range(count):
        if i == 0:
            function = ShotFunction.ESTABLISH
            scale = ShotScale.LS if count > 1 else keyword_to_scale(concrete)
            move = CameraMove.PAN
        elif i == count - 1:
            function = ShotFunction.PAYOFF
            scale = ShotScale.CU
            move = CameraMove.DOLLY_IN
        else:
            function = ShotFunction.CONTEXT
            scale = keyword_to_scale(concrete)
            move = CameraMove.STATIC
        specs.append(
            ShotSpec(
                scene_number=scene_number,
                shot_index=i,
                narrative_beats=concrete,
                subject_concrete=concrete,
                scale=scale,
                move=move,
                function=function,
                mood="dim",
                screen_direction="neutral",
                intensity=0.3 + 0.4 * (i / max(1, count - 1)),
                target_duration_s=2.5,
            )
        )
    return specs


def _cache_get(scene_text: str) -> list[ShotSpec] | None:
    d = cache_dir()
    db = d / "director_cache.sqlite"
    if not db.exists():
        return None
    key = _cache_key(scene_text)
    try:
        conn = sqlite3.connect(str(db))
        row = conn.execute(
            "SELECT shots_json FROM director_cache WHERE key=?", (key,)
        ).fetchone()
        conn.close()
    except sqlite3.Error:
        return None
    if row:
        try:
            data = json.loads(row[0])
            if isinstance(data, list):
                return [ShotSpec(**x) if isinstance(x, dict) else x for x in data]
        except Exception:
            return None
    return None


def _cache_put(scene_text: str, specs: list[ShotSpec]) -> None:
    d = cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    db = d / "director_cache.sqlite"
    key = _cache_key(scene_text)
    try:
        conn = sqlite3.connect(str(db))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS director_cache (key TEXT PRIMARY KEY, shots_json TEXT)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO director_cache (key, shots_json) VALUES (?, ?)",
            (key, json.dumps([s.model_dump(mode="json") for s in specs])),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error:
        pass


def run_director(
    scene_text: str,
    scene_number: int,
    story_context: str = "",
    *,
    llm_fn=None,
) -> list[ShotSpec]:
    """LLM-first director with deterministic fallback. NEVER returns empty.

    llm_fn: callable(prompt, model=None, **kw) -> str | None. When None, uses
    the real LLM path via src.services.llm_service with key rotation. If the
    LLM call raises or returns unparseable, falls back to deterministic.
    """
    cached = _cache_get(scene_text)
    if cached:
        print("cinema director_source: cached")
        return cached

    spec_list: list[ShotSpec] | None = None
    if os.getenv("CINEMA_DIRECTOR_ENABLED", "false").lower() == "true":
        try:
            prompt = build_director_prompt(scene_text, story_context)
            raw = None
            if llm_fn is not None:
                raw = llm_fn(prompt)
            else:
                from src.services.llm_service import llm_service

                model = (
                    os.getenv("CINEMA_DIRECTOR_MODEL")
                    or os.getenv("SCRIPT_MODEL")
                    or "openai/gpt-4o-mini"
                )
                raw = llm_service._chat_free_resilient(
                    None, model, [{"role": "user", "content": prompt}],
                    max_tokens=1500, temperature=0.3,
                )
            spec_list = parse_director_json(raw)
            if spec_list is None:
                spec_list = []
            if spec_list:
                print("cinema director_source: llm")
                _cache_put(scene_text, spec_list)
                return spec_list
        except Exception as e:
            print(f"cinema director LLM failed, using deterministic: {e}")

    fallback = deterministic_director(scene_text, scene_number)
    print("cinema director_source: deterministic")
    return fallback
