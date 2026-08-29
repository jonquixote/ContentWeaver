# Studio S6: Shell Thin + Cleanup Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align surrounding pages with Studio: thin Dashboard (project list → resume in Studio), clean Settings (API keys + model assignments only), delete the old wizard, redirect `/create`, final E2E verification.

**Architecture:** Rebuild `Dashboard.jsx` as project cards (title/status/resume-in-Studio/archive-delete). Rebuild `SettingsPage.jsx` down to two cards: API keys provider management + model assignment card (moves from old wizard's model-card concept). Wizard UI deleted; `/studio` becomes the only creation surface.

**Tech Stack:** React, existing `ApiService`, vitest, Playwright smoke harness (temp dir evidence pattern established in 2026-08-26/27 sessions).

**Spec:** `docs/superpowers/specs/2026-08-27-studio-flow-design.md` · **Depends:** S5.

---

### Task 1: Thin Dashboard

**Files:**
- Modify: `money_weaver_frontend/src/components/Dashboard.jsx` (rewrite)
- Test: `money_weaver_frontend/src/__tests__/dashboard.test.jsx`

View: header `CONTENTWEAVER STUDIO` + saved indicator; grid of project cards: title, workflow type badge, status chip (draft/processing/completed), open (→ /projects/:id), resume in Studio (→ /studio/:id when draft), delete. One "New project" CTA → /studio.

- [ ] **Step 1: Failing test**

```jsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Dashboard from '@/components/Dashboard'
import ApiService from '@/services/api'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => (p) => window.__nav(p) }
})

it('lists projects with resume-in-Studio for drafts', async () => {
  window.__nav = vi.fn()
  vi.spyOn(ApiService, 'getProjects').mockResolvedValue([
    { id: 1, title: 'Old', status: 'completed', workflow_type: 'assembler' },
    { id: 2, title: 'Draft', status: 'draft', workflow_type: 'assembler' },
  ])
  render(<Dashboard />)
  await screen.findByText('Draft')
  const resumeBtn = await screen.findByRole('button', { name: /resume/i })
  fireEvent.click(resumeBtn)
  expect(window.__nav).toHaveBeenCalledWith('/studio/2')
})

it('single New project CTA goes to /studio', async () => {
  window.__nav = vi.fn()
  vi.spyOn(ApiService, 'getProjects').mockResolvedValue([])
  render(<Dashboard />)
  await screen.findByRole('button', { name: /new project/i })
  fireEvent.click(screen.getByRole('button', { name: /new project/i }))
  expect(window.__nav).toHaveBeenCalledWith('/studio')
})
```

- [ ] **Step 2: RED** — current Dashboard fails these shapes.

- [ ] **Step 3: Implement** — rewrite Dashboard with studio tokens (card grid, studio-root background, join url params in resume). Use existing `getProjects`, `deleteProject(id)` (confirm first). Keep component self-fetch with tan query or plain effect (existing pattern: dashboard currently fetches via ApiService.getProjects).

- [ ] **Step 4: GREEN** — tests pass.

- [ ] **Step 5: Commit** — `feat: Dashboard rebuild — project cards, resume-in-Studio, single CTA`

---

### Task 2: Settings cleanup (two cards)

**Files:**
- Modify: `money_weaver_frontend/src/components/SettingsPage.jsx` (rewrite)
- Test: `money_weaver_frontend/src/__tests__/settings.test.jsx`

Two cards ONLY: (1) API Keys — provider list (openrouter/nvidia/fal), key add/test/delete via `getApiKeys/addApiKey/testApiKey/deleteApiKey` (note: api gets by `user_id` param; test expects passing current user id). (2) Model assignments — five tasks (idea/script/enhance/voice_tts/video_gen) with ModelPicker per kind, GET/PUT `/api/model-assignments`.

- [ ] **Step 1: Failing test**

```jsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import SettingsPage from '@/components/SettingsPage'
import ApiService from '@/services/api'
import { useAuthStore } from '@/store/authStore'

vi.mock('@/hooks/useModels', () => ({ useModels: () => ({ data: { models: [{ id: 'm1', label: 'M1' }] } }) }))
vi.mock('@/components/ModelPicker', () => ({ default: ({ value, onChange, kinds }) => <select aria-label={kinds.join(',')} value={value ?? ''} onChange={(e) => onChange(e.target.value || null)}><option value="">Auto</option><option value="m1">M1</option></select> }))

it('renders exactly two sections', async () => {
  useAuthStore.setState({ user: { id: 1 } })
  vi.spyOn(ApiService, 'getApiKeys').mockResolvedValue({ api_keys: [] })
  vi.spyOn(ApiService, 'getModelAssignments').mockResolvedValue({ assignments: {} })
  render(<SettingsPage />)
  await screen.findByText(/api keys/i)
  await screen.findByText(/model assignments/i)
  expect(screen.queryByText(/profile/i)).toBeNull()
})

it('assignment PUT fires on change', async () => {
  useAuthStore.setState({ user: { id: 1 } })
  vi.spyOn(ApiService, 'getApiKeys').mockResolvedValue({ api_keys: [] })
  vi.spyOn(ApiService, 'getModelAssignments').mockResolvedValue({ assignments: { script: null } })
  const put = vi.spyOn(ApiService, 'updateModelAssignments').mockResolvedValue({})
  render(<SettingsPage />)
  await screen.findByText(/model assignments/i)
  fireEvent.change(screen.getByLabelText('text'), { target: { value: 'm1' } })
  await waitFor(() => expect(put).toHaveBeenCalledWith({ assignments: { script: 'm1' } }))
})
```

- [ ] **Step 2: RED** — fails.

- [ ] **Step 3: Implement** — rewrite to exactly two cards; drop unrelated sections/tasks.

- [ ] **Step 4: GREEN** — tests pass.

- [ ] **Step 5: Commit** — `feat: Settings rebuild — two cards (api keys, model assignments)`

---

### Task 3: Delete wizard + redirect /create

**Files:**
- Delete: `money_weaver_frontend/src/components/VideoCreationWizard.jsx`
- Delete: `money_weaver_frontend/src/__tests__/wizardGenerative.test.jsx`
- Modify: `money_weaver_frontend/src/App.jsx` — `/create` → `<Navigate to="/studio" replace />`

- [ ] **Step 1:** Search references: `grep -rn "VideoCreationWizard" money_weaver_frontend/src` — only App.jsx. Any other spec test importing it → remove.

- [ ] **Step 2:** App.jsx route change:

```jsx
<Route path="/create" element={<Navigate to="/studio" replace />} />
```

Delete the import.

- [ ] **Step 3:** `npx vitest run` green; `npx vite build` ok.

- [ ] **Step 4: Commit** — `refactor: remove VideoCreationWizard; /create redirects to /studio`

---

### Task 4: Full E2E verification + close-out

- [ ] **Step 1:** Gates: `npx vitest run` all green; backend pytest subset still green.

- [ ] **Step 2:** Playwright E2E (temp smoke harness pattern from earlier sessions): register → dashboard → New project → /studio → premise (manual text: suggest needs LLM key so type manually) → script (draft fallback via backend canonical) → storyboard scenes render → render config → review (assert summary) → create (mocked or 503-toasted gracefully). Screenshot evidence to temp dir.

- [ ] **Step 3:** Update `.superpowers/sdd/progress.md` with S1..S6 lines + E2E results; commit + push; reiterate review loop per subagent-driven-development until reviewers return APPROVED.

---

### Out of scope (unchanged per spec)

- Renderer/pipeline internals untouched.
- `/voices` and `/projects/:id` pages unchanged.
