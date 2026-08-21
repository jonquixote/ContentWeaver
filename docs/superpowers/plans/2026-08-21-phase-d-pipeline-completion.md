# Phase D: Pipeline Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every inert feature from Phase C — correct caption colors, persisted transcripts, real scene detection, music bed with voice ducking, voice_engine actually read, faster-whisper pinned.

**Architecture:** All changes are backend grafts behind existing interfaces. Music mixing happens in `video_tasks` before `assemble_video` (assembly_service untouched). Scene detection replaces the stub inside `viral_detector.detect_scenes`. Transcript persists via new nullable `Project.transcript` column + Alembic migration chained on `a3f1c9d24e07`.

**Tech Stack:** PySceneDetect 0.7.1 (already installed), ffmpeg sidechaincompress/amix, SQLAlchemy + Alembic, pytest.

**Repo facts:** Repo root `/Volumes/JOHNNY DISK/MoneyWeaver` (space in path — quote). Python: `money_weaver_backend/venv/bin/python -m pytest` (venv activate is broken). Baseline: 360 backend tests passing. Migration chain head: `a3f1c9d24e07` (voices_voice_engine). Niches already carry a `music:` mood key (e.g. `general.yaml:13 → music: neutral`).

---

### Task 1: ASS caption BGR color fix

**Files:**
- Modify: `money_weaver_backend/src/services/video/captions.py:54-62`
- Test: `money_weaver_backend/tests/test_captions.py`

- [ ] **Step 1: Write failing test**

Append to `money_weaver_backend/tests/test_captions.py`:

```python
def test_build_ass_highlight_is_bgr_for_libass():
    from src.services.video.captions import build_ass
    transcript = [{"word": "Hi", "start": 0.0, "end": 0.5}]
    ass = build_ass(transcript, {"captions": {"highlight": "#D32F2F", "font": "Arial"}})
    # RGB D32F2F -> libass &HBBGGRR& == 2F2FD3
    assert "\\c&H2F2FD3&" in ass
    assert "D32F2F" not in ass
```

Also update the existing nested-niche test (`test_captions.py`, currently asserts `"D32F2F"` and
`"\c&D32F2F&"` appear): change those assertions to expect `\\c&H2F2FD3&`.

- [ ] **Step 2: Run test to verify it fails**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_captions.py -v --no-cov`
Expected: FAIL — current code emits `\c&D32F2F&` (RGB).

- [ ] **Step 3: Implement**

In `money_weaver_backend/src/services/video/captions.py`, replace lines 56 and 62:

```python
    color = highlight.lstrip('#').upper() or '00FF88'
```

with:

```python
    rgb = highlight.lstrip('#').upper() or '00FF88'
    if len(rgb) != 6:
        rgb = '00FF88'
    # libass PrimaryColour is &HBBGGRR& (BGR byte order), not RGB hex.
    color = rgb[4:6] + rgb[2:4] + rgb[0:2]
```

and the Dialogue line becomes:

```python
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{{\\c&H{color}&}}{word}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_captions.py -v --no-cov`
Expected: PASS (all, including updated legacy assertions).

- [ ] **Step 5: Commit**

```bash
git add money_weaver_backend/src/services/video/captions.py money_weaver_backend/tests/test_captions.py
git commit -m "fix: ASS highlight colors emitted as libass BGR (&HBBGGRR&)"
```

---

### Task 2: Project.transcript column + persistence

**Files:**
- Modify: `money_weaver_backend/src/models/project.py:17-21`
- Create: `money_weaver_backend/migrations/versions/b7e1d2c3a4f5_project_transcript.py`
- Modify: `money_weaver_backend/src/tasks/video_tasks.py` (assembler task, after TTS)
- Test: `money_weaver_backend/tests/test_transcript_persistence.py`

- [ ] **Step 1: Write failing test**

Create `money_weaver_backend/tests/test_transcript_persistence.py`:

```python
def test_assembler_persists_transcript(client, auth_headers, db_session, monkeypatch):
    """After assembler task runs, project.transcript holds whisper word JSON."""
    import json
    from fastapi_app.routers import generation as gen_mod
    from src.models.project import Project

    fake_words = [{"word": "Hello", "start": 0.0, "end": 0.5}]
    monkeypatch.setattr(
        "src.tasks.video_tasks.extract_transcript_words",
        lambda audio_path: fake_words,
    )
    monkeypatch.setattr(
        "fastapi_app.routers.generation.generate_assembler_video_task.delay",
        lambda **k: type("R", (), {"id": "celery-x"})(),
    )

    p = Project(title="t", description="d", user_id=1, workflow_type="assembler")
    db_session.add(p)
    db_session.commit()

    from src.tasks.video_tasks import persist_transcript
    persist_transcript(p.id, fake_words)
    db_session.expire_all()
    assert json.loads(db_session.get(Project, p.id).transcript) == fake_words


def test_project_model_has_transcript_column():
    from src.models.project import Project
    assert hasattr(Project, 'transcript')
```

Note: check how existing tests obtain `client`/`auth_headers` fixtures (see
`tests/conftest.py`) and reuse identically; adjust `user_id=1` to the fixture's real user id
pattern used by other model tests (grep `Project(` in tests/ for the convention).

- [ ] **Step 2: Run test to verify it fails**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_transcript_persistence.py -v --no-cov`
Expected: FAIL — `Project` has no attribute `transcript`; `persist_transcript` undefined.

- [ ] **Step 3: Add column to model**

In `money_weaver_backend/src/models/project.py`, after the `script` line add:

```python
    transcript = get_db().Column(get_db().Text)  # JSON list of {word,start,end}
```

- [ ] **Step 4: Create Alembic migration**

Create `money_weaver_backend/migrations/versions/b7e1d2c3a4f5_project_transcript.py`,
copying the header/style of `a3f1c9d24e07_voices_voice_engine.py` exactly (same imports,
naming convention) with:

```python
revision: str = 'b7e1d2c3a4f5'
down_revision: Union[str, Sequence[str], None] = 'a3f1c9d24e07'

def upgrade() -> None:
    op.add_column('project', sa.Column('transcript', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('project', 'transcript')
```

(Verify the real table name by grepping `__tablename__` / the baseline migration
`ce8c11da5074_baseline_schema.py` for the projects table — use whatever name it uses; if the
model relies on default naming it will be `project`.)

- [ ] **Step 5: Implement persistence helpers in video_tasks.py**

Add near `write_voice_audio` (line ~81):

```python
def extract_transcript_words(audio_path):
    """Word-level transcript via faster-whisper; [] on any failure."""
    try:
        from src.services.video.viral_detector import transcribe
        return transcribe(audio_path)
    except Exception:
        return []


def persist_transcript(project_id, words):
    """Best-effort transcript persistence; never raises."""
    try:
        from fastapi_app.db import SessionLocal
        from src.models.project import Project
        import json
        session = SessionLocal()
        try:
            proj = session.get(Project, project_id)
            if proj is not None:
                proj.transcript = json.dumps(words)
                session.commit()
        finally:
            session.close()
    except Exception:
        pass
```

Check how sibling tasks create DB sessions inside tasks (grep `create_app_context` /
`SessionLocal` in video_tasks.py) and match that pattern instead if different.

In `generate_assembler_video_task`, immediately after the successful
`audio_file = write_voice_audio(...)` call (~line 294), add:

```python
                    words = extract_transcript_words(audio_file)
                    if words:
                        persist_transcript(project_id, words)
```

- [ ] **Step 6: Wire YouTube captions to the persisted transcript**

In `money_weaver_backend/src/services/providers/youtube_uploader.py`, find `_upload_captions`
(~line 585). It already reads `getattr(project, 'transcript', None)` — now that the column
exists, parse it: if `project.transcript` is a JSON string, `json.loads` it before building the
SRT via `export_srt`. Show the exact edited hunk in the report.

- [ ] **Step 7: Run tests**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_transcript_persistence.py money_weaver_backend/tests/test_youtube.py -v --no-cov`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add money_weaver_backend/src/models/project.py money_weaver_backend/migrations/versions/b7e1d2c3a4f5_project_transcript.py money_weaver_backend/src/tasks/video_tasks.py money_weaver_backend/src/services/providers/youtube_uploader.py money_weaver_backend/tests/test_transcript_persistence.py
git commit -m "feat: persist whisper transcript on Project; activate YT caption upload"
```

---

### Task 3: Pin faster-whisper

**Files:**
- Modify: `money_weaver_backend/requirements.txt` (comment block near line 99)

- [ ] **Step 1: Determine installed version**

Run: `money_weaver_backend/venv/bin/pip show faster-whisper | grep -E "^Version|^License"`
Record version and license (expect MIT).

- [ ] **Step 2: Pin it**

Replace the faster_whisper comment lines (~99-101) with:

```text
# faster_whisper (MIT) is lazy-imported by viral_detector; pinned for
# reproducibility. Install is optional at runtime but required for viral clips.
faster-whisper==<VERSION_FROM_STEP_1>
```

If License is not MIT, STOP and report instead of pinning.

- [ ] **Step 3: Verify suite unaffected**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_viral.py -q --no-cov`
Expected: PASS (tests mock transcribe; pin changes nothing at runtime).

- [ ] **Step 4: Commit**

```bash
git add money_weaver_backend/requirements.txt
git commit -m "chore: pin faster-whisper <VERSION> (MIT)"
```

---

### Task 4: Real scene detection (replace stub)

**Files:**
- Modify: `money_weaver_backend/src/services/video/viral_detector.py:34-50`
- Test: `money_weaver_backend/tests/test_viral.py`

- [ ] **Step 1: Write failing tests**

Append to `money_weaver_backend/tests/test_viral.py`:

```python
class _FakeFrameTime:
    def __init__(self, seconds):
        self._s = seconds
    def get_seconds(self):
        return self._s


def test_detect_scenes_runs_content_detector(monkeypatch):
    from src.services.video import viral_detector as vd

    class FakeVM:
        def __init__(self, paths): pass
        def set_downscale_factor(self): pass
        def start(self): pass

    class FakeSM:
        def __init__(self): self.added = []
        def add_detector(self, d): self.added.append(d)
        def detect_scenes(self, frame_source): pass
        def get_scene_list(self):
            return [
                ((_FakeFrameTime(0.0), _FakeFrameTime(4.0))),
                ((_FakeFrameTime(4.0), _FakeFrameTime(9.5))),
            ]

    calls = {}
    def fake_sm():
        calls['sm'] = FakeSM()
        return calls['sm']

    monkeypatch.setattr(vd, "_VideoManager", FakeVM)
    monkeypatch.setattr(vd, "_SceneManager", fake_sm)
    scenes = vd.detect_scenes("/tmp/fake.mp4")
    assert scenes == [(0.0, 4.0), (4.0, 9.5)]


def test_detect_scenes_merges_short_scenes(monkeypatch):
    from src.services.video import viral_detector as vd
    merged = vd._merge_short_scenes([(0.0, 0.4), (0.4, 2.0), (2.0, 6.0)], min_len=1.0)
    assert merged[0][0] == 0.0 and merged[-1] == (2.0, 6.0)
    assert all((e - s) >= 1.0 or i == len(merged) - 1 for i, (s, e) in enumerate(merged))


def test_no_key_fallback_now_returns_scene_cuts(monkeypatch):
    from src.services.video import viral_detector as vd
    monkeypatch.setattr(vd, "transcribe", lambda p: [])
    monkeypatch.setattr(vd, "detect_scenes", lambda p: [(0.0, 5.0), (5.0, 10.0)])
    def gemini_fail(t, s): raise RuntimeError("no key")
    monkeypatch.setattr(vd, "call_gemini", gemini_fail)
    clips = vd.detect_viral_moments("/tmp/v.mp4", count=2)
    assert clips == [
        {"start": 0.0, "end": 5.0, "score": 0.0, "hook": ""},
        {"start": 5.0, "end": 10.0, "score": 0.0, "hook": ""},
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_viral.py -v --no-cov`
Expected: FAIL — `_VideoManager`/`_SceneManager` attributes don't exist; fallback returns [].

- [ ] **Step 3: Implement**

In `viral_detector.py`, replace the whole `detect_scenes` stub (lines 34-50) with:

```python
# Indirection points so tests can patch scenedetect classes without sys.modules hacks.
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
```

Then fix `_scene_cut_fallback` (~line 102): verify it handles `scenes=[]` without
ZeroDivisionError, and normalize each returned cut to the full clip shape so downstream clip
extraction is uniform:

```python
    return [{"start": s, "end": e, "score": 0.0, "hook": ""}
            for s, e in scenes[:count]]

- [ ] **Step 4: Run tests**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_viral.py -v --no-cov`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests --no-cov`
Expected: all green (360+ baseline).

```bash
git add money_weaver_backend/src/services/video/viral_detector.py money_weaver_backend/tests/test_viral.py
git commit -m "feat: real PySceneDetect scene boundaries replace detect_scenes stub"
```

---

### Task 5: Music bed + voice ducking

**Files:**
- Create: `money_weaver_backend/src/services/video/music_service.py`
- Create: `money_weaver_backend/music/manifest.yaml` (empty tracks list)
- Create: `money_weaver_backend/music/README.md`
- Modify: `money_weaver_backend/src/tasks/video_tasks.py` (assembler, after voice write ~294)
- Test: `money_weaver_backend/tests/test_music_service.py`

- [ ] **Step 1: Write failing tests**

Create `money_weaver_backend/tests/test_music_service.py`:

```python
import os


def test_pick_music_returns_none_when_manifest_missing(monkeypatch, tmp_path):
    from src.services.video import music_service as ms
    monkeypatch.setattr(ms, "_MANIFEST_PATH", str(tmp_path / "missing.yaml"))
    assert ms.pick_music("tech", duration=30) is None


def test_pick_music_matches_niche_mood(monkeypatch, tmp_path):
    from src.services.video import music_service as ms
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "tracks:\n"
        "  - file: upbeat_01.mp3\n"
        "    mood: energetic\n"
        "  - file: calm_01.mp3\n"
        "    mood: neutral\n"
    )
    monkeypatch.setattr(ms, "_MANIFEST_PATH", str(manifest))
    monkeypatch.setattr(ms, "_MUSIC_DIR", str(tmp_path))
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    pick = ms.pick_music("general", duration=30)
    assert pick == os.path.join(str(tmp_path), "calm_01.mp3")


def test_pick_music_skips_missing_files(monkeypatch, tmp_path):
    from src.services.video import music_service as ms
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("tracks:\n  - file: gone.mp3\n    mood: neutral\n")
    monkeypatch.setattr(ms, "_MANIFEST_PATH", str(manifest))
    monkeypatch.setattr(ms, "_MUSIC_DIR", str(tmp_path))
    assert ms.pick_music("general", duration=30) is None


def test_mix_voice_music_builds_duck_cmd(tmp_path):
    from src.services.video.music_service import mix_voice_music
    voice = tmp_path / "voice.wav"
    music = tmp_path / "music.mp3"
    out = tmp_path / "mixed.wav"
    cmd = mix_voice_music(str(voice), str(music), str(out))
    joined = " ".join(cmd)
    assert "sidechaincompress" in joined and "amix" in joined
    assert cmd[0] == "ffmpeg"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_music_service.py -v --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.video.music_service'`.

- [ ] **Step 3: Implement music_service.py**

Create `money_weaver_backend/src/services/video/music_service.py`:

```python
"""Royalty-free music bed selection + ffmpeg ducking mix.

Music files are NOT committed to git (licensing). music/manifest.yaml maps
track files to moods; niches/*.yaml carry a `music:` mood key. Empty or
missing manifest => silent videos, exactly as before.
"""
import os
import random

import yaml

_MUSIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "music",
)
_MANIFEST_PATH = os.path.join(_MUSIC_DIR, "manifest.yaml")

_MOOD_ALIASES = {
    "energetic": {"energetic", "upbeat", "sport", "gaming"},
    "calm": {"calm", "neutral", "ambient"},
    "corporate": {"corporate", "business", "finance", "news", "education"},
}


def _load_tracks():
    try:
        with open(_MANIFEST_PATH) as fh:
            data = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        return []
    return data.get("tracks") or []


def pick_music(niche, duration=None):
    """Return an absolute path to a music file matching the niche's mood, or None."""
    niche_profile = None
    try:
        from src.services.providers.niche_profile import load as load_niche
        niche_profile = load_niche(niche)
    except Exception:
        niche_profile = None
    mood = ((niche_profile or {}).get("music") or "neutral").lower()
    allowed = _MOOD_ALIASES.get(mood, {mood})
    candidates = [
        os.path.join(_MUSIC_DIR, t["file"])
        for t in _load_tracks()
        if str(t.get("mood", "")).lower() in allowed
        and os.path.exists(os.path.join(_MUSIC_DIR, t.get("file", "")))
    ]
    return random.choice(candidates) if candidates else None


def mix_voice_music(voice_path, music_path, out_path, music_volume=0.3):
    """Duck music under voice via sidechaincompress; returns the ffmpeg cmd list.

    Caller is responsible for subprocess.run(cmd, check=True).
    """
    filter_complex = (
        f"[1:a]volume={music_volume}[m];"
        f"[0:a]asplit=2[sc][mix];"
        f"[sc][m]sidechaincompress=threshold=0.05:ratio=10:attack=5:release=300[comp];"
        f"[comp][m]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )
    return [
        "ffmpeg", "-y",
        "-i", voice_path,
        "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-ac", "2",
        out_path,
    ]
```

- [ ] **Step 4: Create manifest + README**

`money_weaver_backend/music/manifest.yaml`:

```yaml
# Royalty-free music library manifest. Files are NOT in git — drop CC0/
# licensed tracks next to this file (Pixabay Audio, FreePD) and list them here.
# moods must match niches/*.yaml `music:` keys (aliases in music_service).
tracks: []
```

`money_weaver_backend/music/README.md`: two sentences pointing at Pixabay Audio / FreePD
(CC0), naming the manifest format, and noting files stay uncommitted (add `music/*.mp3` to
.gitignore — check whether `money_weaver_backend/.gitignore` exists; if not, root `.gitignore`).

- [ ] **Step 5: Wire into assembler task**

In `video_tasks.py` `generate_assembler_video_task`, after the `audio_file =
write_voice_audio(...)` block and after Task 2's transcript lines, add:

```python
                    mixed_audio = _maybe_mix_music(audio_file, niche_id, work_dir=work_dir)
                    if mixed_audio:
                        audio_file = mixed_audio
```

and add the helper near `write_voice_audio`:

```python
def _maybe_mix_music(voice_path, niche_id, work_dir=None):
    """Mix a mood-matched music bed under the voice track. Never raises;
    returns mixed path or None (silent-video behavior preserved)."""
    try:
        import os
        import subprocess
        from src.services.video.music_service import mix_voice_music, pick_music
        music_path = pick_music(niche_id or "general")
        if not music_path:
            return None
        out = os.path.join(work_dir or os.path.dirname(voice_path),
                           f"mixed_{os.path.basename(voice_path)}")
        subprocess.run(mix_voice_music(voice_path, music_path, out),
                       check=True, capture_output=True, timeout=300)
        return out
    except Exception:
        return None
```

Match the actual variable names in the task body (`niche_id`, `work_dir` may be named
differently — grep the surrounding lines first and adapt).

- [ ] **Step 6: Run tests + full suite**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_music_service.py -v --no-cov` then full suite.
Expected: PASS / all green.

- [ ] **Step 7: Commit**

```bash
git add money_weaver_backend/src/services/video/music_service.py money_weaver_backend/music/ money_weaver_backend/src/tasks/video_tasks.py money_weaver_backend/tests/test_music_service.py .gitignore
git commit -m "feat: mood-matched music bed with sidechain ducking (Verticals music.py port)"
```

---

### Task 6: Read voice_engine at the synthesis call site

**Files:**
- Modify: `money_weaver_backend/src/tasks/video_tasks.py` (~line 288-294, cloned-voice branch)
- Test: `money_weaver_backend/tests/test_video_tasks_voice.py`

- [ ] **Step 1: Write failing test**

Append to `money_weaver_backend/tests/test_video_tasks_voice.py` (match its existing mocking
style — read the file first):

```python
def test_assembler_passes_voice_engine_to_synthesize(client, auth_headers, db_session, monkeypatch):
    """voice.voice_engine column must reach tts_client.synthesize."""
    captured = {}

    def fake_synthesize(text, reference_audio_url=None, **kwargs):
        captured["engine"] = kwargs.get("voice_engine")
        return b"RIFFfake"

    monkeypatch.setattr("src.tasks.video_tasks.tts_client.synthesize", fake_synthesize)
    # ... drive generate_assembler_video_task with a Voice whose voice_engine='edge',
    # using the same fixtures/mocks the neighboring tests use (copy their setup verbatim,
    # changing only the assertion target). Assert captured["engine"] == "edge".
    assert captured.get("engine") == "edge"
```

The implementer MUST open `test_video_tasks_voice.py`, copy the full setup of the closest
existing assembler-voice test, and only change what the assertion needs — do not invent a new
harness.

- [ ] **Step 2: Run test to verify it fails**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_video_tasks_voice.py -v --no-cov`
Expected: FAIL — engine never passed (None).

- [ ] **Step 3: Implement**

At the cloned-voice synthesis call (~line 288-294), add the kwarg:

```python
wav_bytes = tts_client.synthesize(
    ...,
    voice_engine=getattr(voice_model, "voice_engine", None),
)
```

Adapt to the real call shape found in the file. If the free-path branch also resolves a Voice
row, wire it there too; otherwise leave the free path alone.

- [ ] **Step 4: Run tests + commit**

Run focused then full suite. Expected: green.

```bash
git add money_weaver_backend/src/tasks/video_tasks.py money_weaver_backend/tests/test_video_tasks_voice.py
git commit -m "feat: thread voices.voice_engine through to tts_client.synthesize"
```

---

### Task 7: Phase D close-out

- [ ] **Step 1:** Full backend suite: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests --no-cov` — all green, coverage ≥55.
- [ ] **Step 2:** Live smoke: boot uvicorn on a scratch sqlite DB, register/login, GET /api/niches, POST one assembler generation with mocked Celery eager mode if feasible; confirm no 500s.
- [ ] **Step 3:** Update `.superpowers/sdd/progress.md` with Phase D summary line.
