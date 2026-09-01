# Cinema Plan E — Critic Loop (pre-render verification)

Date: 2026-08-31
Status: Design (pre-implementation)
Scope: `money_weaver_backend/src/services/cinema/critic_service.py`.
Depends on Plan C (`TimelinePlan`) + Plan A (`ShotSpec`). Hosted VLM only
(no local VLM on Intel).

## Goal

Validate the timeline plan before ffmpeg by scoring a storyboard (middle frame
per planned shot + spec overlay) against each ShotSpec and the whole arc. Failed
rows re-plan with the critique appended to `avoid_clip_ids`.

## Design

- Build storyboard images per plan row (ffmpeg keyframe + spec text overlay).
- Hosted VLM (Gemini/OpenRouter via existing key rotation) scores each row:
  scale progression, tonal arc, duplicate subjects, screen-direction continuity.
- On row failure → re-plan that stage with critique appended to
  `avoid_clip_ids`; bounded iterations (config `CINEMA_CRITIC_MAX_ROUNDS`, default 2).
- Cheap: runs on thumbnails, before ffmpeg; gated by `CINEMA_CRITIC_ENABLED`,
  off by default (tests pass absent). Degrades to "accept" when no VLM available.

## Config

```
CINEMA_CRITIC_ENABLED=false
CINEMA_CRITIC_MAX_ROUNDS=2
CINEMA_CRITIC_IMAGE_SIZE=320
```

## Acceptance

- With critic enabled + VLM stubbed to always-pass, plan unchanged (test).
- With VLM stubbed to always-fail, bounded re-plan and never infinite-loop.
- Storyboard generator produces one image per plan row (unit test).

## Non-goals

- Does not re-render assembled video; gates the plan only.
- No local VLM.
