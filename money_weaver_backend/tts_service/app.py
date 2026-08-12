"""MoneyWeaver TTS microservice — real zero-shot voice cloning with MOSS-TTS-Nano-100M-ONNX.

Runs ONNX inference on CPU (port 8001). Model weights (~728MB) lazy-download on
the first /tts (or /warmup) request; never bundled or committed.
"""
import io
import os
import sys
import tempfile
import threading

import numpy as np
import soundfile as sf
import torch
import torchaudio
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

# MOSS-TTS-Nano source clone lives next to this file (created by setup, git-ignored).
REPO_DIR = os.getenv(
    "MOSS_TTS_REPO",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "MOSS-TTS-Nano"),
)
# Insert after '' (CWD) so `import app` resolves to THIS service, not the repo's
# MOSS-TTS-Nano/app.py, while still exposing onnx_tts_runtime / moss_tts_nano.
if REPO_DIR not in sys.path:
    sys.path.insert(1, REPO_DIR)

OUTPUT_SAMPLE_RATE = int(os.getenv("MOSS_TTS_SAMPLE_RATE", "24000"))  # match Kokoro pipeline
TTS_THREADS = int(os.getenv("MOSS_TTS_THREADS", "4"))

app = FastAPI(title="MoneyWeaver TTS (MOSS-TTS-Nano-ONNX)")

_model = None
_model_lock = threading.Lock()
_synth_lock = threading.Lock()  # onnx runtime is not thread-safe (rng / manifest mutation)


class TTSRequest(BaseModel):
    text: str
    reference_audio_url: str | None = None  # local path or http(s) url
    voice_id: str | None = None
    model: str = "moss-nano"


def load_model():
    """Lazily build + cache the MOSS-TTS ONNX runtime (in-memory)."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        from onnx_tts_runtime import EXECUTION_PROVIDER_CPU, OnnxTtsRuntime

        runtime = OnnxTtsRuntime(
            model_dir=os.getenv("MOSS_TTS_MODEL_DIR") or None,
            thread_count=TTS_THREADS,
            do_sample=True,
            sample_mode="fixed",
            execution_provider=EXECUTION_PROVIDER_CPU,
        )
        runtime.warmup()  # exercise every onnx session before declaring ready
        _model = runtime
    return _model


def _resolve_reference_audio(reference_audio_url: str) -> tuple[str, str | None]:
    """Return (local_wav_path, temp_path_to_cleanup_or_None)."""
    if reference_audio_url.startswith(("http://", "https://")):
        import requests

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        try:
            resp = requests.get(reference_audio_url, timeout=120, stream=True)
            resp.raise_for_status()
            with open(tmp.name, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    fh.write(chunk)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise
        return tmp.name, tmp.name
    path = os.path.expanduser(reference_audio_url)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"reference_audio_url not found: {path}")
    return path, None


def _to_mono_resampled(waveform: np.ndarray, native_sr: int) -> np.ndarray:
    """MOSS codec emits 48kHz stereo; convert to mono at OUTPUT_SAMPLE_RATE."""
    audio = np.asarray(waveform, dtype=np.float32)
    if audio.ndim == 1:
        audio = audio.reshape(-1, 1)
    tensor = torch.from_numpy(audio).transpose(0, 1)  # (channels, samples)
    if tensor.shape[0] > 1:
        tensor = tensor.mean(dim=0, keepdim=True)
    if native_sr != OUTPUT_SAMPLE_RATE:
        tensor = torchaudio.functional.resample(tensor, native_sr, OUTPUT_SAMPLE_RATE)
    return tensor.squeeze(0).detach().cpu().numpy()


@app.get("/health")
def health():
    return {"ok": True, "model_ready": _model is not None}


@app.post("/tts")
def tts(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(400, "text required")
    if not req.reference_audio_url:
        raise HTTPException(400, "reference_audio_url required for cloning")
    try:
        runtime = load_model()
    except Exception as exc:
        raise HTTPException(503, f"Model load failed: {exc}") from exc

    try:
        ref_path, ref_cleanup = _resolve_reference_audio(req.reference_audio_url)
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Reference audio fetch failed: {exc}") from exc
    tmp_out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_out.close()
    try:
        with _synth_lock:
            result = runtime.synthesize(
                text=req.text,
                prompt_audio_path=ref_path,
                output_audio_path=tmp_out.name,
                do_sample=True,
                sample_mode="fixed",
                enable_wetext=False,  # skip pynini (no Intel-Mac wheel)
                enable_normalize_tts_text=True,
            )
        waveform = np.asarray(result["waveform"], dtype=np.float32)
        mono = _to_mono_resampled(waveform, int(result["sample_rate"]))
        buf = io.BytesIO()
        sf.write(buf, mono, OUTPUT_SAMPLE_RATE, format="WAV", subtype="PCM_16")
        return Response(
            content=buf.getvalue(),
            media_type="audio/wav",
            headers={
                "X-Sample-Rate": str(OUTPUT_SAMPLE_RATE),
                "X-Source-Sample-Rate": str(int(result["sample_rate"])),
                "X-Duration-Seconds": f"{len(mono) / OUTPUT_SAMPLE_RATE:.2f}",
            },
        )
    except Exception as exc:
        raise HTTPException(500, f"TTS inference failed: {exc}") from exc
    finally:
        for path in filter(None, (ref_cleanup, tmp_out.name)):
            try:
                os.unlink(path)
            except OSError:
                pass


@app.post("/warmup")
def warmup():
    """Force model download + load (optional; normally lazy on first /tts)."""
    try:
        load_model()
    except Exception as exc:
        raise HTTPException(503, f"Model load failed: {exc}") from exc
    return {"ok": True, "model_ready": True}
