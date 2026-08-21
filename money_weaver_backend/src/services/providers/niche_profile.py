import os
import re
from pathlib import Path

import yaml

_NICHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "niches",
)

_NICHE_ID_RE = re.compile(r"[a-z0-9_-]{1,32}")


def list_niches():
    if not os.path.isdir(_NICHE_DIR):
        return []
    return sorted(
        f[:-5]
        for f in os.listdir(_NICHE_DIR)
        if f.endswith(".yaml") and not f.startswith(".")
    )


def load(niche_id: str) -> dict:
    if not re.fullmatch(r"[a-z0-9_-]{1,32}", niche_id):
        raise ValueError(f"invalid niche_id: {niche_id}")
    # Resolve and ensure path stays inside _NICHE_DIR (traversal guard)
    base = Path(_NICHE_DIR).resolve()
    path = (base / f"{niche_id}.yaml").resolve()
    try:
        if not path.is_relative_to(base):
            raise ValueError(f"invalid niche_id: {niche_id}")
    except AttributeError:
        # Python <3.9 fallback
        if os.path.commonpath([str(path), str(base)]) != str(base):
            raise ValueError(f"invalid niche_id: {niche_id}")
    if not path.is_file():
        raise FileNotFoundError(niche_id)
    with open(path) as fh:
        return yaml.safe_load(fh)


def inject_prompt(base: str, niche: dict) -> str:
    tone = niche.get("tone", "neutral")
    hooks = ", ".join(niche.get("hooks", [])[:3])
    forb = ", ".join(niche.get("forbidden", [])[:2])
    wc = niche.get("word_count", 150)
    extra = f"\nTone: {tone}. Hooks: {hooks}. Avoid: {forb}. Target {wc} words. Only use research facts."
    return base + extra
