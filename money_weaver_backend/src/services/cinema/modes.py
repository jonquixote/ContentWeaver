from __future__ import annotations

from pydantic import BaseModel

from src.services.cinema.types import MontageMode


class ModeConfig(BaseModel):
    w1: float = 1.0   # semantic (embedding/caption-sim to spec)
    w2: float = 1.0   # typed match (scale/move/function)
    w3: float = 1.0   # neighbor term (tonal continuity or contrast)
    w4: float = 0.5   # quality (res, duration, no watermark)
    w5: float = 0.8   # MMR diversity penalty
    w6: float = 0.5   # usage cooldown
    rhythmic: bool = True   # tie duration to motion_energy
    progressive_scale: bool = True  # prefer LS->MS->CU


DEFAULTS: dict[MontageMode, ModeConfig] = {
    MontageMode.METRIC: ModeConfig(w1=0.8, w2=1.0, w3=0.0, w4=0.5, w5=0.8, w6=0.5, rhythmic=False, progressive_scale=True),
    MontageMode.RHYTHMIC: ModeConfig(w1=1.0, w2=1.0, w3=0.6, w4=0.7, w5=0.8, w6=0.5, rhythmic=True, progressive_scale=True),
    MontageMode.TONAL: ModeConfig(w1=0.9, w2=1.0, w3=1.5, w4=0.4, w5=0.7, w6=0.5, rhythmic=False, progressive_scale=True),
    MontageMode.OVERTONAL: ModeConfig(w1=1.0, w2=1.0, w3=1.0, w4=0.5, w5=0.8, w6=0.5, rhythmic=True, progressive_scale=True),
    MontageMode.INTELLECTUAL: ModeConfig(w1=1.0, w2=1.0, w3=-1.0, w4=0.5, w5=0.8, w6=0.5, rhythmic=False, progressive_scale=False),
}


def get_mode_config(mode: MontageMode) -> ModeConfig:
    return DEFAULTS[mode]
