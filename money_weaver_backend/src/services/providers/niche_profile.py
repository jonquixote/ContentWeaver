import os

import yaml

_NICHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "niches",
)


def list_niches():
    return sorted([f[:-5] for f in os.listdir(_NICHE_DIR) if f.endswith(".yaml")])


def load(niche_id: str) -> dict:
    path = os.path.join(_NICHE_DIR, f"{niche_id}.yaml")
    if not os.path.exists(path):
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
