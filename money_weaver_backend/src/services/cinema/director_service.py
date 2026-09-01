from __future__ import annotations

import json
import re

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
