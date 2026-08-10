# MoneyWeaver Full Upgrade — Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade MoneyWeaver from a prototype (fake auth, stubbed features, no tests, no commits) into a production-grade finance-video generation platform.

**Architecture:** Monorepo. Flask backend + React/Vite frontend today. Phase 7 migrates backend to FastAPI. Each phase is independently shippable and testable; phases run sequentially.

**Tech Stack (target):**
- Backend: Flask 3.1 (→ FastAPI 0.136 + SQLModel in Phase 7), Celery 5.5 + Redis, SQLite (→ Postgres optional), PyJWT + Argon2, Cloudflare R2 (boto3), Chatterbox TTS, Kokoro fallback, FFmpeg/MoviePy 2.x assembly
- Frontend: React 19 + Vite, TypeScript (incremental), TanStack Query v5, Zustand v5, TipTap, Vidstack, shadcn/ui + Tailwind v4, Clerk (optional)
- Testing: pytest + pytest-asyncio + httpx, Vitest, testcontainers

## Execution Order (impact ÷ effort)

1. **Phase 0 — Hygiene & Safety** (critical, ~1-2 days)
2. **Phase 1 — Auth & Security** (critical, ~2-3 days)
3. **Phase 2 — Core Product Features** (format presets, bolded captions, templates, thumbnails) (~1 week)
4. **Phase 4 — Storage (R2)** (high, ~1 day)
5. **Phase 5 — Frontend Modernization** (TanStack, TipTap, Vidstack, Zustand, redesign) (~1-2 weeks)
6. **Phase 3 — Real Voice Cloning** (Chatterbox) (product moat, ~1 week)
7. **Phase 6 — Testing** (half day + ongoing)
8. **Phase 7 — FastAPI Migration** (medium priority, ~2-4 days)

## Phase Plan Index

| File | Phase | Priority |
|---|---|---|
| `2026-08-10-01-phase0-hygiene.md` | Hygiene & Safety | Critical |
| `2026-08-10-02-phase1-auth.md` | Auth & Security | Critical |
| `2026-08-10-03-phase2-core-features.md` | Core Product Features | High |
| `2026-08-10-04-phase3-voice-cloning.md` | Real Voice Cloning | Moa |
| `2026-08-10-05-phase4-storage.md` | Storage (R2) | High |
| `2026-08-10-06-phase5-frontend.md` | Frontend Modernization | High |
| `2026-08-10-07-phase6-testing.md` | Testing | Medium |
| `2026-08-10-08-phase7-fastapi.md` | FastAPI Migration | Medium |

## Global Constraints (all phases)

- Python 3.12+ (venv `money_weaver_backend/venv312`), Node 20+, pnpm
- Backend runs on port 5004 (`/api` prefix), frontend on Vite dev port
- Never commit secrets. `.env` stays gitignored
- Every task ends with a commit (git init at repo root first, Phase 0)
- SQLite at `money_weaver_backend/src/database/app.db`; `DATABASE_URL` env override respected
- CORS restricted to frontend origin (not `*`) after Phase 1
- LLM default model: `groq/llama-3.3-70b-versatile`; LiteLLM master key from env
- MoneyPrinterTurbo (github.com/harry0703/MoneyPrinterTurbo) is the reference architecture for the video pipeline — reuse its provider-abstraction pattern, don't fork

## Key Findings Driving This Plan

- **No auth on most endpoints** — IDOR on `/users/<id>`, `/projects/<id>`, `/api-keys/user/<id>`; `/auth/me` returns hardcoded user
- **Hardcoded secrets** — `sk-master-key-change-me`, fallback SECRET_KEY in `src/main.py:23`
- **Voice cloning is simulated** — `advanced_tts_service.clone_voice()` ignores reference audio, uses `af_heart`
- **Frontend FormData bug** — `api.js:28-30` stringifies any object body, breaking `cloneVoice` multipart
- **XSS** — `dangerouslySetInnerHTML` renders LLM script text unescaped (Dashboard.jsx:222-227)
- **No logout UI**, fake dashboard data, stubbed VoiceCloning/Profile/Settings
- **Zero tests, zero git commits**, debug scripts and `._*` junk files everywhere
- **`/auth/me` mock**, `userId = 1` hardcoded in SettingsPage and Wizard
