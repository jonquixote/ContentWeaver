from __future__ import annotations

from src.services.cinema.clip import ClipRecord
from src.services.cinema.hash_util import hamming_distance
from src.services.cinema.modes import get_mode_config
from src.services.cinema.shot import ShotSpec
from src.services.cinema.types import MontageMode

DEDUP_HAMMING = 6
DEDUP_DURATION_TOLERANCE_S = 1.0
SCALE_ORDER = ["ecu", "cu", "mcu", "ms", "mls", "ls", "els", "abstract"]
_SCALE_CONTRAST_BONUS = 3.0


def semantic_sim(clip: ClipRecord, spec: ShotSpec) -> float:
    """Embedding/caption similarity when available; neutral 0.0 otherwise."""
    if clip.embedding is not None and len(clip.embedding) > 0:
        # Simplified: users of Plan A have no embeddings; token-space stub.
        # Later plans replace this with cosine over real CLIP vectors.
        return 0.5
    return 0.0


def typed_match(clip: ClipRecord, spec: ShotSpec) -> float:
    """Scale/move/function match. None typed fields are NEUTRAL (0.0), never
    a negative mismatch."""
    score = 0.0
    if clip.scale is not None:
        same = abs(SCALE_ORDER.index(clip.scale.value) - SCALE_ORDER.index(spec.scale.value))
        score += 1.0 - min(same, 4) * 0.2  # closer scale = higher
    if clip.move is not None:
        score += 1.0 if clip.move == spec.move else 0.2
    return score


def neighbor_term(clip: ClipRecord, prev: ClipRecord | None, mode: MontageMode) -> float:
    if prev is None:
        return 0.0
    same_scale = clip.scale is not None and prev.scale is not None and clip.scale == prev.scale
    same_move = clip.move is not None and prev.move is not None and clip.move == prev.move
    similarity = (1.0 if same_scale else 0.0) + (1.0 if same_move else 0.0)
    if mode == MontageMode.INTELLECTUAL:
        # deliberate contrast: penalize sameness
        return -similarity * _SCALE_CONTRAST_BONUS
    # tonal/other: reward continuity
    return similarity


def quality(clip: ClipRecord) -> float:
    q = 0.0
    if clip.width and clip.width >= 1080:
        q += 0.5
    if clip.height and clip.height >= 720:
        q += 0.3
    if clip.duration_s >= 4.0:
        q += 0.2
    return min(q, 1.0)


def dedup_reject(clip: ClipRecord, chosen: list[ClipRecord] | None) -> bool:
    """Reject only when Hamming <= DEDUP_HAMMING AND duration within
    +/- DEDUP_DURATION_TOLERANCE_S of an already-chosen clip.

    Pinned to image hash, never URL/provider-ID. The duration guard protects
    against flat-thumbnail aHash collisions: two clips can share an all-zero
    hash (flat colors) yet differ in length, and must NOT be deduped.
    """
    if not chosen or clip.average_hash is None:
        return False
    for c in chosen:
        if c.average_hash and hamming_distance(clip.average_hash, c.average_hash) <= DEDUP_HAMMING:
            if abs(clip.duration_s - c.duration_s) <= DEDUP_DURATION_TOLERANCE_S:
                return True
    return False


def _distance_penalty(dist: float, mode: MontageMode) -> float:
    return 1.0 * (1.0 - dist)  # closer (lower dist) -> bigger penalty


def score(
    clip: ClipRecord,
    spec: ShotSpec,
    *,
    mode: MontageMode,
    prev: ClipRecord | None,
    chosen: list[ClipRecord],
) -> float:
    cfg = get_mode_config(mode)
    total = (
        cfg.w1 * semantic_sim(clip, spec)
        + cfg.w2 * typed_match(clip, spec)
        + cfg.w3 * neighbor_term(clip, prev, mode)
        + cfg.w4 * quality(clip)
    )
    if dedup_reject(clip, chosen):
        total -= 10.0  # strong penalty; MMR also drops these
    if clip.used_in_video_ids:
        total -= cfg.w6 * len(clip.used_in_video_ids)
    return total


def rank_candidates(
    clips: list[ClipRecord],
    spec: ShotSpec,
    *,
    mode: MontageMode = MontageMode.OVERTONAL,
    prev: ClipRecord | None = None,
    chosen: list[ClipRecord] | None = None,
) -> list[ClipRecord]:
    """MMR-style ranking: pick highest-scoring, penalize proximity to chosen.

    `chosen` = clips already selected for EARLIER shots (cross-shot context).
    Dedup and MMR diversity evaluate against `picked + chosen`, so a near-dup
    of any previously-selected clip is excluded from this shot's ranking.
    """
    prior = chosen if chosen is not None else []
    remaining = list(clips)
    picked: list[ClipRecord] = []
    while remaining:
        best = None
        best_c = float("-inf")
        selected_so_far = picked + prior
        for c in remaining:
            if dedup_reject(c, selected_so_far):
                continue
            s = score(c, spec, mode=mode, prev=prev, chosen=selected_so_far)
            # MMR diversity: subtract similarity to already-selected (hash proximity)
            for pc in selected_so_far:
                if c.average_hash and pc.average_hash:
                    dist = hamming_distance(c.average_hash, pc.average_hash) / 64.0
                    s -= _distance_penalty(dist, mode)
            if s > best_c:
                best_c = s
                best = c
        if best is None:
            break
        picked.append(best)
        remaining.remove(best)
    return picked
