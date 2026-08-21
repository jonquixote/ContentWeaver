# Phase E: Chatterbox Voice Cloning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add MIT-licensed zero-shot voice cloning (Chatterbox) as an opt-in provider in the TTS fallback chain, replacing the aging MOSS reference-cloning path when enabled.

**Architecture:** New provider module `chatterbox_tts.py` mirrors `edge_tts.py`'s lazy-import seam. `tts_client.synthesize` gains engine value `"chatterbox"`; the cloned-voice chain becomes MOSS → Chatterbox (flag on) → Edge → Kokoro → gTTS. Flag `CHATTERBOX_ENABLED=false` default — the package is NOT installed in the main venv (heavy torch stack); tests fake it via module seams.

**Tech Stack:** resemble-ai/chatterbox (`chatterbox-tts`, MIT code+weights), torchaudio, existing tts_client seams.

**Repo facts:** `/Volumes/JOHNNY DISK/MoneyWeaver`; `money_weaver_backend/venv/bin/python -m pytest`; baseline 360+ tests. `tts_client.py:13 VALID_ENGINES = {"moss","edge","kokoro","gtts"}`; cloned path at `tts_client.py:94+` (`reference_audio_url is not None and voice_engine != "edge"` → MOSS try, `_edge()` fallback). `edge_tts.py` is the pattern to copy for lazy-import + tempfile lifecycle.

---

### Task 1: chatterbox_tts provider module

**Files:**
- Create: `money_weaver_backend/src/services/providers/chatterbox_tts.py`
- Test: `money_weaver_backend/tests/test_chatterbox_tts.py`

- [ ] **Step 1: Write failing test**

Create `money_weaver_backend/tests/test_chatterbox_tts.py`:

```python
import pytest


def _fake_chatterbox_module(monkeypatch):
    """Inject fake chatterbox.tts + torchaudio modules into sys.modules."""
    import sys
    import types

    fake_cb = types.ModuleType("chatterbox")
    fake_tts = types.ModuleType("chatterbox.tts")

    class FakeModel:
        sr = 24000
        def generate(self, text, audio_prompt_path=None, exaggeration=0.5):
            # plain object; only torchaudio.save touches it
            return object()

    fake_tts.ChatterboxTTS = type(
        "ChatterboxTTS", (),
        {"from_pretrained": classmethod(lambda cls, device=None: FakeModel())}
    )
    fake_cb.tts = fake_tts

    saved = {}
    fake_ta = types.ModuleType("torchaudio")
    def fake_save(path, wav, sr):
        with open(path, "wb") as fh:
            fh.write(b"RIFFfake-wavdata")
        saved["path"] = path
    fake_ta.save = fake_save
    monkeypatch.setitem(sys.modules, "chatterbox", fake_cb)
    monkeypatch.setitem(sys.modules, "chatterbox.tts", fake_tts)
    monkeypatch.setitem(sys.modules, "torchaudio", fake_ta)
    return saved


def test_disabled_flag_raises(monkeypatch):
    from src.services.providers import chatterbox_tts as cb
    monkeypatch.setattr(cb, "CHATTERBOX_ENABLED", False)
    with pytest.raises(RuntimeError, match="disabled"):
        cb.synthesize("hello", "/tmp/ref.wav")


def test_synthesize_returns_wav_bytes(monkeypatch, tmp_path):
    from src.services.providers import chatterbox_tts as cb
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"RIFFref")
    _fake_chatterbox_module(monkeypatch)
    monkeypatch.setattr(cb, "CHATTERBOX_ENABLED", True)
    out = cb.synthesize("hello world", str(ref))
    assert isinstance(out, bytes) and len(out) > 0
```

Note: `torch` is NOT installed in the main venv (boot warning confirms) — the fakes above
ensure no real torch/chatterbox import ever happens in tests.

- [ ] **Step 2: Run test to verify it fails**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_chatterbox_tts.py -v --no-cov`
Expected: FAIL — `No module named 'src.services.providers.chatterbox_tts'`.

- [ ] **Step 3: Implement**

Create `money_weaver_backend/src/services/providers/chatterbox_tts.py`:

```python
"""Chatterbox zero-shot voice cloning (MIT, resemble-ai/chatterbox).

Opt-in: requires `pip install chatterbox-tts` (pulls torch/torchaudio) and
CHATTERBOX_ENABLED=true. Clones a voice from a ~5-10s reference wav.
"""
import os

import torchaudio  # noqa: F401  (runtime dep of chatterbox save path)

CHATTERBOX_ENABLED = os.getenv("CHATTERBOX_ENABLED", "false").lower() == "true"

_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        from chatterbox.tts import ChatterboxTTS
        _MODEL = ChatterboxTTS.from_pretrained(device="cpu")
    return _MODEL


def synthesize(text, reference_audio_path, exaggeration=0.5):
    """Clone-speak `text` in the reference voice. Returns wav bytes."""
    if not CHATTERBOX_ENABLED:
        raise RuntimeError("chatterbox disabled (set CHATTERBOX_ENABLED=true)")
    model = _get_model()
    import tempfile

    wav = model.generate(text, audio_prompt_path=reference_audio_path,
                         exaggeration=exaggeration)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        torchaudio.save(tmp.name, wav, model.sr)
        with open(tmp.name, "rb") as fh:
            return fh.read()
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass
```

Remove the top-level `import torchaudio` if it breaks collection in the main venv (torch
absent) — move it inside `synthesize()` after the flag check instead. Prefer the lazy form:

```python
def synthesize(text, reference_audio_path, exaggeration=0.5):
    if not CHATTERBOX_ENABLED:
        raise RuntimeError("chatterbox disabled (set CHATTERBOX_ENABLED=true)")
    import torchaudio
    ...
```

- [ ] **Step 4: Run tests**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_chatterbox_tts.py -v --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add money_weaver_backend/src/services/providers/chatterbox_tts.py money_weaver_backend/tests/test_chatterbox_tts.py
git commit -m "feat: Chatterbox voice-cloning provider (MIT, opt-in flag)"
```

---

### Task 2: Slot into tts_client chain

**Files:**
- Modify: `money_weaver_backend/src/services/tts_client.py:13,94-120`
- Test: `money_weaver_backend/tests/test_tts_client.py`

- [ ] **Step 1: Write failing tests**

Append to `money_weaver_backend/tests/test_tts_client.py` (match its existing mock style):

```python
def test_cloned_voice_uses_chatterbox_when_enabled(monkeypatch):
    from src.services import tts_client
    monkeypatch.setattr(tts_client.chatterbox_mod, "CHATTERBOX_ENABLED", True)
    monkeypatch.setattr(tts_client.chatterbox_mod, "synthesize",
                        lambda text, ref, **k: b"RIFFcb")
    # block MOSS like the existing MOSS-failure tests do
    monkeypatch.setattr(tts_client.requests, "post",
                        lambda *a, **k: (_ for _ in ()).throw(tts_client.requests.ConnectionError("down")))
    out = tts_client.synthesize("hi", reference_audio_url="/tmp/ref.wav")
    assert out == b"RIFFcb"


def test_engine_chatterbox_rejected_when_disabled(monkeypatch):
    from src.services import tts_client
    monkeypatch.setattr(tts_client.chatterbox_mod, "CHATTERBOX_ENABLED", False)
    with pytest.raises(ValueError, match="CHATTERBOX_ENABLED"):
        tts_client.synthesize("hi", voice_engine="chatterbox")
```

(Adapt `requests.post` blocking to whatever the file's existing MOSS-mock helper uses.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_tts_client.py -v --no-cov`
Expected: FAIL — no `chatterbox_mod` attribute; engine rejected as unknown.

- [ ] **Step 3: Implement**

In `tts_client.py`:

1. Near imports add: `from src.services.providers import chatterbox_tts as chatterbox_mod`
2. Line 13 becomes: `VALID_ENGINES = {"moss", "edge", "kokoro", "gtts", "chatterbox"}`
3. In the validation branch (~72), allow `"chatterbox"` explicitly but raise at call time when
   the flag is off:

```python
    if voice_engine == "chatterbox" and not chatterbox_mod.CHATTERBOX_ENABLED:
        raise ValueError(
            "voice_engine 'chatterbox' requires CHATTERBOX_ENABLED=true "
            "and pip install chatterbox-tts"
        )
```

4. In the cloned-voice chain (~94), after the MOSS attempt fails and before `_edge()`:

```python
        if chatterbox_mod.CHATTERBOX_ENABLED:
            try:
                return chatterbox_mod.synthesize(text, reference_audio_url)
            except Exception:
                pass  # fall through to Edge
```

Keep the existing behavior when the flag is off (chain identical to today).

- [ ] **Step 4: Run tests + full suite**

Run focused then `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests --no-cov`.
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add money_weaver_backend/src/services/tts_client.py money_weaver_backend/tests/test_tts_client.py
git commit -m "feat: Chatterbox slot in cloned-voice TTS chain behind CHATTERBOX_ENABLED"
```

---

### Task 3: Requirements note + docs

**Files:**
- Modify: `money_weaver_backend/requirements.txt` (near the edge-tts license comment block)

- [ ] **Step 1:** Add commented block (NOT installed by default):

```text
# --- Optional: Chatterbox voice cloning (MIT) ---
# Heavy (torch/torchaudio). Install manually on workers that need cloning:
#   pip install chatterbox-tts==0.1.4   # verify latest via `pip index versions chatterbox-tts`
# Then set CHATTERBOX_ENABLED=true.
```

Verify the current version string with
`money_weaver_backend/venv/bin/pip index versions chatterbox-tts 2>/dev/null || curl -s https://pypi.org/pypi/chatterbox-tts/json | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"`
and confirm license is MIT via the PyPI classifiers before writing it into the comment.

- [ ] **Step 2:** Full suite green; commit:

```bash
git add money_weaver_backend/requirements.txt
git commit -m "docs: optional chatterbox-tts install instructions (MIT)"
```

---

### Task 4: Phase E close-out

- [ ] **Step 1:** Full suite green; coverage ≥55.
- [ ] **Step 2:** Manual check (documented, not committed): with `pip install chatterbox-tts` in a scratch venv and a 7s reference wav, `CHATTERBOX_ENABLED=true venv/bin/python -c "from src.services.providers import chatterbox_tts; print(len(chatterbox_tts.synthesize('test','ref.wav')))"` produces bytes. If machine cannot install torch, record SKIP with reason.
- [ ] **Step 3:** Update `.superpowers/sdd/progress.md`.
