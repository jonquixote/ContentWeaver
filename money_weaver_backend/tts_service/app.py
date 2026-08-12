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

# Reference-audio contract (global constraint): 3-20s, WAV/MP3, >=16kHz.
MIN_REF_DURATION = 3.0
MAX_REF_DURATION = 20.0
MIN_REF_SAMPLE_RATE = 16000
MAX_REF_DOWNLOAD_BYTES = 25 * 1024 * 1024  # ~25MB cap on remote ref downloads
AUDIO_CONTENT_TYPES = {
    "audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave",
    "audio/mpeg", "audio/mp3", "audio/mp4", "audio/ogg", "audio/x-m4a",
}

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


def _unlink_quiet(path: str | None) -> None:
    if path:
        try:
            os.unlink(path)
        except OSError:
            pass


def _prepare_reference_audio(path: str) -> tuple[str, str | None]:
    """Enforce the reference-audio contract and normalize to WAV.

    Global constraint: WAV/MP3, 3-20s, >=16kHz. Boundary pre-check runs before
    the model sees the clip so a 1s or 8kHz sample cannot silently produce a
    bad clone. The runtime may still resample internally; this enforces the
    documented input contract regardless.

    Returns (path_for_runtime, cleanup_or_None). The runtime (torchaudio) cannot
    decode MP3, so MP3 references are transcoded to WAV via soundfile.
    """
    try:
        info = sf.info(path)
    except Exception as exc:  # noqa: BLE001 - any read failure = contract violation
        raise HTTPException(400, f"reference_audio unreadable: {exc}") from exc
    if info.format not in ("WAV", "MP3"):
        raise HTTPException(
            400,
            f"reference_audio format '{info.format}' not supported (WAV/MP3 only)",
        )
    if info.samplerate < MIN_REF_SAMPLE_RATE:
        raise HTTPException(
            400,
            f"reference_audio sample rate {info.samplerate}Hz < {MIN_REF_SAMPLE_RATE}Hz required",
        )
    if not (MIN_REF_DURATION <= info.duration <= MAX_REF_DURATION):
        raise HTTPException(
            400,
            f"reference_audio duration {info.duration:.1f}s outside [{MIN_REF_DURATION}-{MAX_REF_DURATION}]s",
        )
    if info.format == "WAV":
        return path, None
    data, sr = sf.read(path, dtype="float32")
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    sf.write(tmp.name, data, sr, format="WAV", subtype="PCM_16")
    return tmp.name, tmp.name


def _resolve_reference_audio(reference_audio_url: str) -> tuple[str, str | None]:
    """Return (local_wav_path, temp_path_to_cleanup_or_None).

    NOTE (exposure): local-path reads accept any path the service process can
    read. The service binds 0.0.0.0:8001 unauthenticated (internal LAN). Keep
    this behind the LAN; do not expose publicly without auth.
    """
    if reference_audio_url.startswith(("http://", "https://")):
        import requests

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        try:
            resp = requests.get(reference_audio_url, timeout=120, stream=True)
            resp.raise_for_status()
            content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if content_type and content_type not in AUDIO_CONTENT_TYPES:
                raise HTTPException(
                    400,
                    f"reference_audio URL content-type '{content_type}' is not audio",
                )
            downloaded = 0
            with open(tmp.name, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    downloaded += len(chunk)
                    if downloaded > MAX_REF_DOWNLOAD_BYTES:
                        raise HTTPException(
                            400,
                            f"reference_audio download exceeds {MAX_REF_DOWNLOAD_BYTES} byte cap",
                        )
                    fh.write(chunk)
        except Exception:
            _unlink_quiet(tmp.name)
            raise
        return tmp.name, tmp.name
    path = os.path.expanduser(reference_audio_url)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"reference_audio_url not found: {path}")
    return path, None


def _to_mono_resampled(waveform: np.ndarray, native_sr: int) -> np.ndarray:
    """MOSS codec emits 48kHz stereo; convert to mono at OUTPUT_SAMPLE_RATE."""
    import torch
    import torchaudio

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

    ref_path = None
    cleanups: list[str] = []
    try:
        ref_path, dl_cleanup = _resolve_reference_audio(req.reference_audio_url)
        if dl_cleanup:
            cleanups.append(dl_cleanup)
        ref_path, norm_cleanup = _prepare_reference_audio(ref_path)
        if norm_cleanup:
            cleanups.append(norm_cleanup)
    except FileNotFoundError as exc:
        for p in cleanups:
            _unlink_quiet(p)
        raise HTTPException(400, str(exc)) from exc
    except HTTPException:
        for p in cleanups:
            _unlink_quiet(p)
        raise
    except Exception as exc:
        for p in cleanups:
            _unlink_quiet(p)
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
        for p in cleanups:
            _unlink_quiet(p)
        _unlink_quiet(tmp_out.name)


@app.post("/warmup")
def warmup():
    """Force model download + load (optional; normally lazy on first /tts)."""
    try:
        load_model()
    except Exception as exc:
        raise HTTPException(503, f"Model load failed: {exc}") from exc
    return {"ok": True, "model_ready": True}
