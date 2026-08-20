import pytest
from src.services.providers.edge_tts import synthesize, list_voices


def test_list_voices():
    voices = list_voices()
    assert "en-US-AriaNeural" in voices


@pytest.mark.asyncio
async def test_synthesize_mocked(monkeypatch):
    async def fake_comm(*a, **k):
        class C:
            async def __aenter__(self): return self

            async def __aexit__(self, *a): pass

            def save(self, p): open(p, "wb").write(b"RIFF fake wav")

        return C()

    monkeypatch.setattr("edge_tts.Communicate", fake_comm)
    wav = await synthesize("Hello world", "en-US-AriaNeural")
    assert wav[:4] == b"RIFF"


def test_tts_client_edge_fallback(monkeypatch):
    async def fake_comm(*a, **k):
        class C:
            def save(self, p): open(p, "wb").write(b"RIFF edge wav")

        return C()

    monkeypatch.setattr("edge_tts.Communicate", fake_comm)
    from src.services.tts_client import synthesize as tts_synth

    wav = tts_synth("hello edge", voice_engine="edge")
    assert wav[:4] == b"RIFF"
