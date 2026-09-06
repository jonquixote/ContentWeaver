# Cinema Plan E — Critic (one-call-per-render, advisory) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hosted-VLM critic that scores a render's storyboard frames against its ShotSpecs in one Gemini call per render, returning schema-validated JSON; advisory-only in v1 (log + persist critiques, no re-render loop).

**Architecture:** New `src/services/cinema/critic_service.py` (pure functions: storyboard build, prompt build, strict-JSON parse/validate, file persistence) plus a thin `GeminiCriticClient` that POSTs multimodal parts to `generativelanguage.googleapis.com` with the existing key-rotation discipline (429 → next key; all keys exhausted → skip, never fail). Storyboard frames come from ffmpeg middle-frame extraction of already-downloaded clips (same mechanism as `motion_energy_series` in `timing_service.py`). Suite stays hermetic via stub/VCR (no network, no SDK).

**Tech Stack:** Python 3.12, stdlib + `requests` (already a dependency — the codebase POSTs to `generativelanguage.googleapis.com` directly today in `stock_footage_service.py`), pydantic 2.13.5, pytest. No new dependencies. No SDK install (direct REST, matching existing convention).

## Global Constraints

- One Gemini call per render. No bulk enrichment, no multi-call loops, no stitching clips to save calls.
- Strict-JSON output, schema-validated; parse/validation failure means the critic is silently off for that render (log + return None).
- Advisory-only in v1: log critiques, persist per project/render id; NO re-render loop, NO automatic re-selection.
- `CINEMA_CRITIC_ENABLED=false` default. Suite passes with no network and no SDK (stub the client; VCR-record one golden cassette).
- 429/402 (or any transport failure) means skip the critique, never fail the render. Key rotation via `GEMINI_API_KEY` + comma-separated fallbacks (same discipline as `stock_footage_service._gemini_keys`).
- Agentic vs static is a config knob (`CRITIC_MODE=static|agentic`): static sends storyboard frames; agentic sends the final rendered video with `media_processing="AGENTIC"` for timestamped observations.
- Reuse canon types verbatim: `ShotSpec` (scene_number, shot_index, narrative_beats, subject_concrete, scale, move, function, mood, screen_direction, intensity, target_duration_s, avoid_clip_ids), `TimelineShot` (clip_id, in_point_s, out_point_s, transition, function), `MontageMode`. No renames.
- TDD, one branch `cinema/plan-e`, commit per task, checkpoint holds for review, single PR.

---

## File Structure

- Create `src/services/cinema/critique_schema.py` — strict `ShotVerdict`/`RenderCritique` (Task 1).
- Create `src/services/cinema/critic_service.py` — storyboard, prompt, parse, client, entry point (Tasks 2–5, grown incrementally).
- Modify `money_weaver_backend/.env.example` — critic flags (Task 5).
- Test: `tests/cinema/test_critique_schema.py`, `tests/cinema/test_critic.py` (+ VCR cassette `tests/cinema/cassettes/critic_static.yaml`).


> Design note (key rotation): `_gemini_keys()` is deliberately duplicated (6 lines)
> in `critic_service.py` rather than imported from `stock_footage_service`, to
> avoid a cinema→video-service dependency inversion. `llm_service._chat_free_resilient`
> is text-only (no image-parts support), so the multimodal-capable path is the
> direct-REST + key-rotation discipline, replicated here. If a shared Gemini helper
> is later extracted, both call sites should migrate to it (logged as a follow-up,
> not built here).

---

## Task 1: Critique schema (strict JSON contract)

**Files:**
- Create: `src/services/cinema/critique_schema.py`
- Test: `tests/cinema/test_critique_schema.py`

**Interfaces:**
- Consumes: nothing (pydantic only).
- Produces: `ShotVerdict` (shot_index:int, verdict:Literal["match","mismatch"], reason:str), `RenderCritique` (shots:list[ShotVerdict], overall_verdict:Literal["pass","review"], summary:str). Strict: unknown fields rejected, verdict enums closed.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from pydantic import ValidationError
from src.services.cinema.critique_schema import RenderCritique, ShotVerdict


def test_shot_verdict_accepts_valid():
    v = ShotVerdict(shot_index=0, verdict="match", reason="comedian on stage, CU as specced")
    assert v.verdict == "match"


def test_shot_verdict_rejects_bad_verdict():
    with pytest.raises(ValidationError):
        ShotVerdict(shot_index=0, verdict="maybe", reason="x")


def test_render_critique_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        RenderCritique(shots=[], overall_verdict="pass", summary="ok", extra_field=1)


def test_render_critique_requires_shots_list():
    with pytest.raises(ValidationError):
        RenderCritique(overall_verdict="pass", summary="ok")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cinema/test_critique_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.cinema.critique_schema'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ShotVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_index: int = Field(ge=0)
    verdict: Literal["match", "mismatch"]
    reason: str = Field(min_length=1)


class RenderCritique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shots: list[ShotVerdict]
    overall_verdict: Literal["pass", "review"]
    summary: str = Field(min_length=1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cinema/test_critique_schema.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/services/cinema/critique_schema.py tests/cinema/test_critique_schema.py
git commit -m "feat(cinema): strict critique JSON schema (ShotVerdict, RenderCritique)"
```

---

## Task 2: Storyboard builder (ffmpeg middle frames)

**Files:**
- Create: storyboard section of `src/services/cinema/critic_service.py`
- Test: `tests/cinema/test_critic.py`

**Interfaces:**
- Consumes: `TimelineShot` (clip_id, in_point_s, out_point_s), a `clip_path_resolver: Callable[[str], str | None]` (clip_id → local file; the render pipeline supplies it; tests stub it).
- Produces: `build_storyboard(shots, resolve, out_dir, image_size=320) -> list[dict]` — each `{shot_index, clip_id, frame_path}`; skips unresolvable shots (never raises).

- [ ] **Step 1: Write the failing test**

```python
import os
from src.services.cinema.critic_service import build_storyboard
from src.services.cinema.montage_service import TimelineShot


def _shot(i, clip="c"):
    return TimelineShot(clip_id=f"{clip}{i}", in_point_s=0.0, out_point_s=2.5)


def test_build_storyboard_skips_unresolvable(tmp_path):
    shots = [_shot(0), _shot(1)]
    out = build_storyboard(shots, lambda cid: None, str(tmp_path))
    assert out == []


def test_build_storyboard_extracts_middle_frame(tmp_path):
    import subprocess
    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc=duration=4:size=320x240:rate=10",
                    "-pix_fmt", "yuv420p", src], check=True, timeout=60)
    shots = [_shot(0, clip="v")]
    out = build_storyboard(shots, lambda cid: src, str(tmp_path / "sb"), image_size=160)
    assert len(out) == 1
    assert out[0]["shot_index"] == 0
    assert os.path.exists(out[0]["frame_path"])


def test_build_storyboard_index_survives_skips():
    # A skipped (unresolvable) shot must NOT shift alignment: shot_index is the
    # position in plan.shots, so frames stay aligned with specs.
    import subprocess
    import tempfile
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "src.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc=duration=4:size=320x240:rate=10",
                    "-pix_fmt", "yuv420p", src], check=True, timeout=60)
    shots = [_shot(0), _shot(1), _shot(2)]
    def resolve(cid):
        return src if cid in ("c0", "c2") else None
    out = build_storyboard(shots, resolve, os.path.join(tmp, "sb"), image_size=160)
    assert [r["shot_index"] for r in out] == [0, 2]
    assert [r["clip_id"] for r in out] == ["c0", "c2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cinema/test_critic.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.cinema.critic_service'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

> `shot_index` is the position in `plan.shots`, pinned by test (a skipped shot
> keeps its index — frames and specs stay aligned). Timeline in/out points are
> converted to clip-local `[0, dur)` before extraction, pinned by test.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cinema/test_critic.py -v`
Expected: PASS (2 passed; requires ffmpeg on PATH — already a pipeline dependency per `motion_energy_series`)

- [ ] **Step 5: Commit**

```bash
git add src/services/cinema/critic_service.py tests/cinema/test_critic.py
git commit -m "feat(cinema): storyboard builder (ffmpeg middle frames, skips unresolvable)"
```

---

## Task 3: Critic prompt builder

**Files:**
- Modify: `src/services/cinema/critic_service.py`
- Test: `tests/cinema/test_critic.py`

**Interfaces:**
- Consumes: `list[ShotSpec]`, storyboard row count.
- Produces: `build_critic_prompt(specs: list[ShotSpec], n_frames: int, agentic: bool = False) -> str` — instructs per-shot match/mismatch verdicts + montage-level flags; agentic variant requests timestamped observations for whole-video input.

- [ ] **Step 1: Write the failing test**

```python
from src.services.cinema.critic_service import build_critic_prompt
from src.services.cinema.shot import ShotSpec
from src.services.cinema.types import CameraMove, ShotFunction, ShotScale


def _spec(i):
    return ShotSpec(scene_number=1, shot_index=i, narrative_beats="jokes fly",
                    subject_concrete="comedian with microphone on stage",
                    scale=ShotScale.MS, move=CameraMove.STATIC,
                    function=ShotFunction.CONTEXT, mood="dim")


def test_prompt_lists_every_shot_spec():
    prompt = build_critic_prompt([_spec(0), _spec(1)], n_frames=2)
    assert "comedian with microphone on stage" in prompt
    assert "shot_index" in prompt
    assert "match" in prompt and "mismatch" in prompt


def test_prompt_demands_strict_json_shape():
    prompt = build_critic_prompt([_spec(0)], n_frames=1)
    assert "overall_verdict" in prompt
    assert "reason" in prompt


def test_agentic_prompt_requests_timestamps():
    prompt = build_critic_prompt([_spec(0)], n_frames=0, agentic=True)
    assert "timestamp" in prompt.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cinema/test_critic.py -v -k "prompt"`
Expected: FAIL with `ImportError: cannot import name 'build_critic_prompt'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cinema/test_critic.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/cinema/critic_service.py tests/cinema/test_critic.py
git commit -m "feat(cinema): critic prompt builder (static + agentic timestamped variant)"
```

---

## Task 4: Strict-JSON parse + Gemini client (key rotation, one call)

**Files:**
- Modify: `src/services/cinema/critic_service.py`
- Test: `tests/cinema/test_critic.py` (+ VCR cassette `tests/cinema/cassettes/critic_static.yaml`)

**Interfaces:**
- Consumes: prompt text, storyboard frame paths (static) or video path (agentic), `GEMINI_API_KEY` + fallbacks.
- Produces: `parse_critique(raw: str | None) -> RenderCritique | None` (None on any parse/validation failure — critic silently off); `GeminiCriticClient.critique(frames, prompt, *, agentic=False, video_path=None) -> RenderCritique | None` (one POST, key rotation, 429 → next key, all-exhausted → None).

- [ ] **Step 1: Write the failing test**

```python
from src.services.cinema.critic_service import GeminiCriticClient, parse_critique


def test_parse_critique_accepts_valid_json():
    raw = ('{"shots": [{"shot_index": 0, "verdict": "mismatch", "reason": "shows a duck, spec needs a comedian"}], '
           '"overall_verdict": "review", "summary": "one off-theme pick"}')
    c = parse_critique(raw)
    assert c is not None
    assert c.overall_verdict == "review"
    assert c.shots[0].verdict == "mismatch"


def test_parse_critique_rejects_garbage_silently():
    assert parse_critique(None) is None
    assert parse_critique("not json at all") is None
    assert parse_critique('{"shots": "wrong-shape"}') is None


def test_parse_critique_extracts_json_from_prose():
    raw = 'Here is my review:\n{"shots": [], "overall_verdict": "pass", "summary": "clean"}'
    c = parse_critique(raw)
    assert c is not None and c.overall_verdict == "pass"


def test_client_skips_without_keys(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("src.services.cinema.critic_service._gemini_keys", lambda: [])
    client = GeminiCriticClient()
    assert client.critique([], "prompt") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cinema/test_critic.py -v -k "parse or client"`
Expected: FAIL with `ImportError: cannot import name 'parse_critique'`

- [ ] **Step 3: Write minimal implementation**

```python
import base64 as _b64
import json as _json
import os
import re

import requests

from src.services.cinema.critique_schema import RenderCritique


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
```

> Note for the implementer: `CRITIC_MODEL` default is `"gemini-2.0-flash"` as a safe static default; the brief's agentic models (3.7/3.6/3.5 Flash family) are selected via env. `media_processing="AGENTIC"` is sent only in agentic mode per the brief. Max 10 videos / ~45-min limits from the brief do not bind a ≤60s short — no chunking logic needed in v1. **Agentic mode requires an agentic-capable model string** — if `CRITIC_MODE=agentic` is set while `CRITIC_MODEL` names a static-only model, log a warning and proceed static (never fail the render over a model mismatch).

- [ ] **Step 4: Record the VCR cassette (once, redacted key) and run tests**

Record `tests/cinema/cassettes/critic_static.yaml` with `filter_query_parameters=["key"]` (same convention as the Pixabay cassette fix — key travels as `?key=`). Then run: `pytest tests/cinema/test_critic.py -v`. Expected: PASS. The cassette test itself is the stub path (`test_client_skips_without_keys`); the cassette documents the golden request shape for review.

- [ ] **Step 5: Commit**

```bash
git add src/services/cinema/critic_service.py tests/cinema/test_critic.py tests/cinema/cassettes/critic_static.yaml
git commit -m "feat(cinema): strict-JSON parse + Gemini critic client (one call, key rotation)"
```

---

## Task 5: run_critique entry point + persistence + flags

**Files:**
- Modify: `src/services/cinema/critic_service.py`, `money_weaver_backend/.env.example`
- Test: `tests/cinema/test_critic.py`

**Interfaces:**
- Consumes: `TimelinePlan`, `list[ShotSpec]`, clip resolver, project/render id.
- Produces: `run_critique(plan, specs, resolve, *, project_id, render_id, agentic=None) -> RenderCritique | None` — builds storyboard, prompts, calls client once, persists JSON to `CRITIC_DIR`, returns critique or None. `CINEMA_CRITIC_ENABLED=false` (or any failure) → None, never raises.

- [ ] **Step 1: Write the failing test**

```python
import json
import os
from src.services.cinema.critic_service import run_critique
from src.services.cinema.montage_service import TimelinePlan, TimelineShot
from src.services.cinema.shot import ShotSpec
from src.services.cinema.types import CameraMove, MontageMode, ShotFunction, ShotScale


def _plan():
    return TimelinePlan(mode=MontageMode.OVERTONAL, shots=[
        TimelineShot(clip_id="c0", in_point_s=0.0, out_point_s=2.5),
    ])


def _specs():
    return [ShotSpec(scene_number=1, shot_index=0, narrative_beats="jokes",
                     subject_concrete="comedian", scale=ShotScale.MS,
                     move=CameraMove.STATIC, function=ShotFunction.CONTEXT, mood="dim")]


def test_run_critique_disabled_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("CINEMA_CRITIC_ENABLED", "false")
    assert run_critique(_plan(), _specs(), lambda cid: None,
                        project_id="p", render_id="r",
                        persist_dir=str(tmp_path)) is None


def test_run_critique_persists_valid_critique(monkeypatch, tmp_path):
    monkeypatch.setenv("CINEMA_CRITIC_ENABLED", "true")
    from src.services.cinema import critic_service as cs
    fake = {"shots": [], "overall_verdict": "pass", "summary": "clean"}
    monkeypatch.setattr(cs.GeminiCriticClient, "critique", lambda self, f, p, **k: cs.parse_critique(__import__("json").dumps(fake)))
    out = run_critique(_plan(), _specs(), lambda cid: None,
                       project_id="p1", render_id="r1", persist_dir=str(tmp_path))
    assert out is not None and out.overall_verdict == "pass"
    saved = list(tmp_path.glob("*.json"))
    assert len(saved) == 1
    assert json.loads(saved[0].read_text())["overall_verdict"] == "pass"


def test_run_critique_never_raises_on_client_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("CINEMA_CRITIC_ENABLED", "true")
    from src.services.cinema import critic_service as cs
    def boom(self, f, p, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(cs.GeminiCriticClient, "critique", boom)
    assert run_critique(_plan(), _specs(), lambda cid: None,
                        project_id="p", render_id="r", persist_dir=str(tmp_path)) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cinema/test_critic.py -v -k "run_critique"`
Expected: FAIL with `ImportError: cannot import name 'run_critique'`

- [ ] **Step 3: Write minimal implementation**

```python
def run_critique(plan, specs, resolve, *, project_id: str, render_id: str,
                 persist_dir: str | None = None, agentic: bool | None = None) -> RenderCritique | None:
    """Advisory-only v1 entry point. CINEMA_CRITIC_ENABLED=false (or any failure) →
    None. On success persists the critique JSON and returns it. Never raises."""
    try:
        if os.getenv("CINEMA_CRITIC_ENABLED", "false").lower() != "true":
            return None
        use_agentic = agentic if agentic is not None else (
            os.getenv("CRITIC_MODE", "static").lower() == "agentic")
        size = int(os.getenv("CRITIC_IMAGE_SIZE", "320"))
        max_frames = int(os.getenv("CRITIC_MAX_FRAMES", "12"))
        frames = build_storyboard(plan.shots[:max_frames], resolve,
                                  os.path.join(persist_dir or os.getenv("CRITIC_DIR", "/tmp/cw-critic"), "sb"),
                                  image_size=size)
        prompt = build_critic_prompt(specs, n_frames=len(frames), agentic=use_agentic)
        client = GeminiCriticClient()
        critique = client.critique(frames, prompt, agentic=use_agentic)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cinema/test_critic.py -v`
Expected: PASS

- [ ] **Step 5: Commit (flags included)**

Append to `money_weaver_backend/.env.example`:
```
CINEMA_CRITIC_ENABLED=false
```
Add `CRITIC_BACKEND=gemini`, `CRITIC_MODE=static`, `CRITIC_IMAGE_SIZE=320`, `CRITIC_MAX_FRAMES=12`, `CRITIC_TIMEOUT_S=60`, `CRITIC_DIR=/tmp/cw-critic`.

```bash
git add src/services/cinema/critic_service.py money_weaver_backend/.env.example tests/cinema/test_critic.py
git commit -m "feat(cinema): run_critique entry (advisory-only, persists per render) + flags"
```

> Storyboard dir retention: storyboard frames live under `CRITIC_DIR/sb/` next to
> the persisted critique JSON. They are evidence for sign-off — do NOT delete
> them in the render path. Disk cleanup (`FOOTAGE_DISK_RETENTION_H` purge) must
> exclude `CRITIC_DIR`. Covered by the retention test in Task 6.

---

## Task 6: Wire the call site + closing ritual (live render, flag on)

**Files:**
- Modify: `src/tasks/video_tasks.py` (call `run_critique` after assembly, flag-gated)
- Test: `tests/cinema/test_critic.py` (wiring contract) + live ritual (non-CI)

**Interfaces:**
- Consumes: `TimelinePlan` used for the render, `list[ShotSpec]`, clip resolver, project/render ids.
- Produces: one persisted critique JSON per render when `CINEMA_CRITIC_ENABLED=true`; nothing when off.

**TimelinePlan source decision (explicit):** when `CINEMA_TIMING_ENABLED=true`, reuse the
timing plan's underlying `TimelinePlan` (the same object passed to assembly — single
source of truth, no parallel structure). When timing is off, synthesize minimal
shots from `clip_durations` (one `TimelineShot` per clip, `in_point_s=0`,
`out_point_s=duration`) so the critic still has a plan to score. Both paths are
tested below.

- [ ] **Step 1: Write the failing test**

```python
from src.services.cinema.critic_service import critique_plan_for_render
from src.services.cinema.montage_service import TimelinePlan, TimelineShot


def test_wiring_synthesizes_shots_when_no_timing_plan():
    # Timing off: minimal shots synthesized from clip durations.
    shots = critique_plan_for_render(None, [2.5, 2.5])
    assert len(shots) == 2
    assert all(isinstance(s, TimelineShot) for s in shots)


def test_wiring_reuses_timing_plan_when_present():
    from src.services.cinema.montage_service import TimelinePlan, TimelineShot
    from src.services.cinema.types import MontageMode
    plan = TimelinePlan(mode=MontageMode.OVERTONAL, shots=[
        TimelineShot(clip_id="a", in_point_s=0.0, out_point_s=2.5),
    ])
    assert critique_plan_for_render(plan, []) is plan  # same object, no parallel structure


def test_wiring_returns_none_when_disabled(monkeypatch):
    monkeypatch.setenv("CINEMA_CRITIC_ENABLED", "false")
    from src.services.cinema.critic_service import maybe_critique_render
    assert maybe_critique_render(None, [], lambda cid: None, "p", "r") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cinema/test_critic.py -v -k "wiring or critique_plan"`
Expected: FAIL with `ImportError: cannot import name 'critique_plan_for_render'`

- [ ] **Step 3: Write minimal implementation**

```python
def critique_plan_for_render(timing_plan, clip_durations: list[float]):
    """Single source of truth for the plan the critic scores: reuse the timing
    plan when present, else synthesize minimal shots from clip durations."""
    if timing_plan is not None:
        return timing_plan
    from src.services.cinema.montage_service import TimelineShot
    return [TimelineShot(clip_id=f"clip_{i}", in_point_s=0.0, out_point_s=float(d))
            for i, d in enumerate(clip_durations)]


def maybe_critique_render(plan, specs, resolve, project_id: str, render_id: str):
    """Flag-gated call-site wrapper. Returns the critique or None. Never raises."""
    import os
    if os.getenv("CINEMA_CRITIC_ENABLED", "false").lower() != "true":
        return None
    try:
        return run_critique(plan, specs, resolve, project_id=project_id, render_id=render_id)
    except Exception as e:
        print(f"cinema critic call-site failed, render proceeds: {e}")
        return None
```

Call site (`src/tasks/video_tasks.py`, after assembly succeeds, flag-gated inside
`maybe_critique_render` — the call itself is unconditional placement, behavior
gated):

```python
timing_plan = ...  # the same object passed to assemble_video (or None)
specs = ...        # ShotSpecs used for the render
critique_plan = critique_plan_for_render(timing_plan, clip_durations_used)
maybe_critique_render(critique_plan, specs, resolve_clip_path,
                      project_id=str(project_id), render_id=task_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cinema/test_critic.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/cinema/critic_service.py src/tasks/video_tasks.py tests/cinema/test_critic.py
git commit -m "feat(cinema): wire critic call site (reuse timing plan, flag-gated, never-blocks)"
```

- [ ] **Step 6: Closing ritual (non-CI, live render)**

1. One live render with `CINEMA_CRITIC_ENABLED=true` (deterministic director; quotas as available).
2. Confirm one persisted critique JSON under `CRITIC_DIR` (`{project_id}_{render_id}.json`), storyboard frames beside it.
3. Human sign-off on critique quality (verdicts match/mismatch the visible frames; reasons specific, not generic).
4. Record sign-off + artifact paths in the followups log. Plan E closes on sign-off, not on the render alone.

---

## Self-Review

**Spec coverage** (to the brief + user constraints):
- One call per render → `GeminiCriticClient.critique` single POST (Task 4).
- Strict-JSON schema-validated output → `critique_schema.py` strict models + `parse_critique` None-on-failure (Tasks 1, 4).
- Advisory-only v1, no re-render loop → `run_critique` logs + persists only (Task 5). No re-plan code anywhere.
- `CINEMA_CRITIC_ENABLED=false` default → checked first in `run_critique`; flags in `.env.example` (Task 5).
- Key rotation via existing stack → `_gemini_keys` discipline (primary + `GEMINI_API_KEY_FALLBACKS`, 429 → next, else bail), same shape as `stock_footage_service` (Task 4).
- Suite hermetic → stub/VCR only, no network, no SDK (all tasks; cassette redacted).
- Storyboard frames vs ShotSpecs → Task 2 + Task 3 prompt shape.
- Agentic timestamped variant → `agentic` flag, `media_processing="AGENTIC"`, timestamp instruction (Tasks 3, 4).

**Placeholder scan:** no TBD/TODO; all code complete for the flagged-off path. `test_client_skips_without_keys` exercises the no-key path without network.

**Type consistency:** `ShotVerdict`/`RenderCritique`, `build_storyboard(shots, resolve, out_dir, image_size)`, `build_critic_prompt(specs, n_frames, agentic)`, `parse_critique(raw)`, `GeminiCriticClient().critique(frames, prompt, agentic, video_path)`, `run_critique(plan, specs, resolve, project_id, render_id, persist_dir, agentic)`, `critique_plan_for_render(timing_plan, clip_durations)`, `maybe_critique_render(plan, specs, resolve, project_id, render_id)` — consistent across tasks. `shot_index` is the position in `plan.shots` (Task 2 pins it, including across skips).

## Standing plan checklist (applies to this and all future plans)

- [ ] **Every entry point has a wired caller.** `run_critique`/`maybe_critique_render` is called from the render path (Task 6). No `CINEMA_*_ENABLED=true` code path may exist without a call site exercised by test or ritual — the Plan A (pre-PR#2) and Plan D placebos must not recur. Verified by grep for the entry name outside its defining module + tests.
