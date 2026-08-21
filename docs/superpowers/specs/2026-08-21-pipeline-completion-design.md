# Pipeline Completion + Voice Cloning + Generative Enablement (Phases D/E/F)

Date: 2026-08-21
Status: Approved direction (follows Modular Shorts Platform Phased C, pushed through b7ae43d)

## Goal

Make every already-built-but-inert feature actually work, mine the two MIT source repos
(openshorts, youtube-shorts-pipeline "Verticals") for their highest-value remaining modules,
add MIT-licensed voice cloning (Chatterbox), and make the ComfyUI generative path real.

## Context

Phase C shipped: niche profiles, Edge TTS, topic discovery, ASS/SRT captions, ComfyUI gateway
(flag-gated), 9:16 reframe, viral moment detection, YouTube private upload + webhooks, frontend
wiring. Live smoke testing found and fixed two runtime bugs (b7ae43d).

Known inert/broken features (from whole-branch review + smoke test):
1. ASS caption highlight colors are RGB (`&RRGGBB&`) but libass expects BGR (`&HBBGGRR&`) — every
   niche's caption color renders wrong.
2. `Project.transcript` does not exist — YouTube caption upload reads `getattr(project,
   'transcript', None)` and always gets None; viral detector re-transcribes instead of reusing.
3. `detect_scenes()` is a stub returning `[]` — without GEMINI_API_KEY, viral detection returns
   zero clips.
4. Videos ship silent — no music bed, no ducking.
5. `voices.voice_engine` column written by T2 but never read at the synthesis call site.
6. `workflows/wan22_t2v_api.json` is a minimal placeholder — COMFY_ENABLED would queue a graph
   that cannot produce real output.
7. faster_whisper unpinned (reproducibility).
8. No local voice cloning despite MOSS reference-cloning being the legacy path.

## Decisions

- **License policy unchanged**: MIT/Apache/BSD freely; LGPL dependency-only (edge-tts stays,
  sign-off pending); AGPL/NC blocked (ultralytics stays out; VibeVoice stays out).
- **Scene detection**: use PySceneDetect `ContentDetector` (BSD-3, already in requirements since
  T7) rather than TransNetV2 weights — zero new deps, CPU-fast, deterministic in CI.
- **Music**: local royalty-free library under `money_weaver_backend/music/` described by
  `manifest.yaml` (file/mood). Repo ships an EMPTY manifest + README pointing at Pixabay/
  FreePD CC0 sources — no copyrighted audio in git. Missing/empty manifest ⇒ graceful no-music.
  Ducking via ffmpeg `sidechaincompress`+`amix` (Verticals music.py pattern), done in
  `video_tasks` BEFORE `assemble_video` so assembly_service stays untouched.
- **Voice cloning**: Chatterbox (MIT code+weights, resemble-ai/chatterbox) as opt-in provider.
  Flag `CHATTERBOX_ENABLED=false` default (heavy torch deps not in main venv today). Slot order
  for cloned voices becomes MOSS → Chatterbox (if enabled) → Edge → Kokoro → gTTS.
- **Generative**: port a real Wan2.2 t2v graph from kijai/ComfyUI-WanVideoWrapper example
  workflows (Apache-2.0) into API-format JSON; `model` param selects fp8 variant template;
  still flag-gated, dev behavior unchanged.
- **Out of scope** (future phases): self-improving analytics loop, i2v stock animation,
  multi-segment >60s stories, TikTok/IG distribution, GPU rental ops.

## Phases

| Phase | Plan | Deliverable |
|---|---|---|
| D | phase-d-pipeline-completion | Correct captions, persisted transcripts, real scene detection, music bed + ducking, voice_engine wired, whisper pinned |
| E | phase-e-chatterbox-voice-cloning | Opt-in MIT voice cloning provider in the TTS chain |
| F | phase-f-generative-enablement | Real Wan2.2 workflow templates + model-variant selection + enabled-path test |

Each phase produces working, testable software independently. Execution order D → E → F;
tasks within a phase are sequential (shared files).

## Testing

Backend pytest fail-under 55 (currently ~62%); all network/model loads mocked; full suite green
before every commit. Frontend untouched except none of these phases require UI changes.
