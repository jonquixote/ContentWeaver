# Studio S2: Shell + Sync + Premise Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Studio shell (`/studio/:projectId?`) with design tokens, stage tabs, draft sync hook, and Stage 1 (Premise) fully working.

**Architecture:** New files under `src/pages/` (Studio), `src/components/studio/` (stage components + shared), `src/hooks/useStudioSync.js`, `src/lib/studioState.js` (state shape + gates). Design tokens as CSS custom properties in `index.css` (no tailwind config churn). API additions extend `src/services/api.js`.

**Tech Stack:** React 18 + react-router v6 (existing in App.jsx), vitest/jsdom, msw (existing test conventions in `src/__tests__/`).

**Spec:** `docs/superpowers/specs/2026-08-27-studio-flow-design.md`

**Depends:** Plan S1 (backend endpoints `POST /api/projects/studio`, `GET/PUT /api/projects/{id}/studio`).

**State contract (shared, do not change without touching every plan):** see S1 header. `studioState.js` MUST export exactly:

```js
export const SCHEMA_VERSION = 1
export const STAGES = [
  { id: 1, label: 'Premise' },
  { id: 2, label: 'Script' },
  { id: 3, label: 'Storyboard' },
  { id: 4, label: 'Render' },
  { id: 5, label: 'Review' },
]
export function defaultStudioState() { /* deep fresh copy of S1 contract */ }
export function validateStage(state, stage, ctx = {}) // -> { ok, errors: [] }
```

Gates: 1 = `premise.text.trim() !== ''`; 2 = `script.title.trim() !== ''` AND ≥1 scene parsed from `scriptHtml`→text (use `jsonToScriptText` + `parseScreenplay` from `src/lib/screenplayBlocks.js` and `src/lib/scriptParser.js`); 3 = ≥1 scene AND total duration within selected preset's min/max (or skip preset check if none selected); 4 = presets empty OR `render.presetId` set; 5 = always true.

---

### Task 1: Design tokens + AIGenButton

**Files:**
- Modify: `money_weaver_frontend/src/index.css`
- Create: `money_weaver_frontend/src/components/studio/AIGenButton.jsx`
- Test: `money_weaver_frontend/src/__tests__/aiGenButton.test.jsx`

- [ ] **Step 1: Failing test**

```jsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import AIGenButton from '@/components/studio/AIGenButton'

describe('AIGenButton', () => {
  it('calls onGenerate and shows spinner while pending', async () => {
    let resolve
    const onGenerate = vi.fn(() => new Promise(r => (resolve = r)))
    render(<AIGenButton label="suggest" onGenerate={onGenerate} />)
    fireEvent.click(screen.getByRole('button', { name: /suggest/i }))
    expect(onGenerate).toHaveBeenCalled()
    expect(await screen.findByRole('status')).toBeInTheDocument()
    resolve()
    await waitFor(() => expect(screen.queryByRole('status')).toBeNull())
  })

  it('surfaces errors via toast, keeps button usable', async () => {
    const onGenerate = vi.fn().mockRejectedValue(new Error('503'))
    render(<AIGenButton label="generate" onGenerate={onGenerate} />)
    fireEvent.click(screen.getByRole('button', { name: /generate/i }))
    await waitFor(() => expect(screen.getByRole('button')).not.toBeDisabled())
  })
})
```

- [ ] **Step 2: RED** — `npx vitest run src/__tests__/aiGenButton.test.jsx` fails (module missing).

- [ ] **Step 3: Implement**

`src/index.css` — append design tokens:

```css
/* Studio design tokens (spec 2026-08-27: technical studio, refined) */
:root {
  --studio-bg: #070b12;
  --studio-surface: #0c121c;
  --studio-card: #111827;
  --studio-border: #1e293b;
  --studio-accent: #22d3ee;
  --studio-text: #f1f5f9;
  --studio-muted: #94a3b8;
}
.studio-root { background: var(--studio-bg); color: var(--studio-text); }
```

`src/components/studio/AIGenButton.jsx`:

```jsx
import { useState } from 'react'
import { Sparkles, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

export default function AIGenButton({ label, onGenerate, disabled }) {
  const [busy, setBusy] = useState(false)
  const handle = async () => {
    if (busy || disabled) return
    setBusy(true)
    try {
      await onGenerate()
    } catch (e) {
      toast.error(e?.message || `${label} failed`)
    } finally {
      setBusy(false)
    }
  }
  return (
    <button
      type="button"
      onClick={handle}
      disabled={disabled || busy}
      aria-label={`AI ${label}`}
      className="inline-flex items-center gap-1 text-xs text-[var(--studio-accent)] hover:opacity-80 disabled:opacity-40 transition-opacity"
    >
      {busy
        ? <Loader2 className="h-3.5 w-3.5 animate-spin" role="status" />
        : <Sparkles className="h-3.5 w-3.5" />}
      {label}
    </button>
  )
}
```

- [ ] **Step 4: GREEN** — same command passes.

- [ ] **Step 5: Commit** — `feat: studio design tokens + AIGenButton`

---

### Task 2: studioState.js + Studio shell + StageTabs + route

**Files:**
- Create: `money_weaver_frontend/src/lib/studioState.js`
- Create: `money_weaver_frontend/src/components/studio/StageTabs.jsx`
- Create: `money_weaver_frontend/src/pages/Studio.jsx`
- Modify: `money_weaver_frontend/src/App.jsx` (add `/studio` + `/studio/:projectId` protected routes)
- Test: `money_weaver_frontend/src/__tests__/studioState.test.jsx`, `src/__tests__/stageTabs.test.jsx`

- [ ] **Step 1: Failing tests**

```jsx
// studioState.test.jsx
import { describe, it, expect } from 'vitest'
import { defaultStudioState, validateStage, SCHEMA_VERSION } from '@/lib/studioState'

describe('studioState', () => {
  it('defaults match S1 contract', () => {
    const s = defaultStudioState()
    expect(s.stage).toBe(1)
    expect(s.schemaVersion).toBe(SCHEMA_VERSION)
    expect(s.premise.durationSec).toBe(60)
    expect(s.render.workflowType).toBe('assembler')
  })
  it('stage 1 gate requires premise text', () => {
    expect(validateStage(defaultStudioState(), 1).ok).toBe(false)
    const s = defaultStudioState(); s.premise.text = 'x'
    expect(validateStage(s, 1).ok).toBe(true)
  })
})
```

```jsx
// stageTabs.test.jsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import StageTabs from '@/components/studio/StageTabs'

it('visits only stages <= furthest unlocked', () => {
  const onGo = vi.fn()
  render(<StageTabs current={2} furthest={3} onGo={onGo} />)
  fireEvent.click(screen.getByRole('button', { name: /storyboard/i }))
  expect(onGo).toHaveBeenCalledWith(3)
  fireEvent.click(screen.getByRole('button', { name: /review/i }))
  expect(onGo).toHaveBeenCalledTimes(1) // stage 5 locked (4 not visited)
})
```

- [ ] **Step 2: RED** — `npx vitest run src/__tests__/studioState.test.jsx src/__tests__/stageTabs.test.jsx` fails.

- [ ] **Step 3: Implement**

Note: ScriptEditor (existing component) takes `value` (HTML string) and emits `onChange(html, text)`. We store BOTH: `scriptHtml` for the editor and `scriptText` (canonical screenplay text, parsed by `parseScriptText`) for gates/storyboard. Do NOT invent a JSON format.

`src/lib/studioState.js`:

```js
import { parseScriptText } from './scriptParser'

export const SCHEMA_VERSION = 1

export const STAGES = [
  { id: 1, label: 'Premise' },
  { id: 2, label: 'Script' },
  { id: 3, label: 'Storyboard' },
  { id: 4, label: 'Render' },
  { id: 5, label: 'Review' },
]

export const DURATIONS = [30, 60, 90, 120, 180, 240, 300]

export function defaultStudioState() {
  return {
    schemaVersion: SCHEMA_VERSION,
    stage: 1,
    premise: { text: '', durationSec: 60, nicheId: '', sequenceProjectId: null },
    script: { title: '', description: '', scriptHtml: '', scriptText: '', characters: [] },
    storyboard: { overrides: {} },
    render: {
      presetId: null, voiceType: 'female', voiceId: null,
      voiceModelOverride: null, workflowType: 'assembler',
      orientation: 'landscape', width: '1920', height: '1080', language: 'en',
    },
    updatedAt: null,
  }
}

export function sceneCount(state) {
  return parseScriptText(state.script?.scriptText || '').scenes.length
}

export function validateStage(state, stage, ctx = {}) {
  const t = (s) => (s || '').trim()
  switch (stage) {
    case 1:
      return { ok: t(state.premise?.text) !== '', errors: t(state.premise?.text) ? [] : ['Premise required'] }
    case 2: {
      const errors = []
      if (!t(state.script?.title)) errors.push('Title required')
      if (sceneCount(state) === 0) errors.push('At least one scene required')
      return { ok: errors.length === 0, errors }
    }
    case 3: {
      if (sceneCount(state) === 0) return { ok: false, errors: ['No scenes'] }
      return { ok: true, errors: [] }
    }
    case 4:
      if (ctx.presets?.length && !state.render?.presetId) {
        return { ok: false, errors: ['Select a preset'] }
      }
      return { ok: true, errors: [] }
    default:
      return { ok: true, errors: [] }
  }
}
```

Note: `scriptTextToHtml`/`jsonToScriptText` — `jsonToScriptText` takes TipTap JSON (`{content:[...]}`), so `state.script.scriptHtml` storage uses TipTap **JSON string**, not HTML. Store `script.scriptJson` (JSON) as canonical; `getJSON()` from editor. Amend defaultState: `script: { title: '', description: '', scriptJson: null, characters: [] }`. Drop `scriptHtml` everywhere.

`src/components/studio/StageTabs.jsx`:

```jsx
import { STAGES } from '@/lib/studioState'

const HUES = { 1: '#22d3ee', 2: '#a78bfa', 3: '#fbbf24', 4: '#34d399', 5: '#f87171' }

export default function StageTabs({ current, furthest, onGo }) {
  return (
    <div className="flex items-center gap-1 px-4 py-2 border-b"
         style={{ borderColor: 'var(--studio-border)' }} role="tablist">
      {STAGES.map((s) => {
        const enabled = s.id <= furthest
        const active = s.id === current
        return (
          <button key={s.id} role="tab" aria-selected={active} disabled={!enabled}
            onClick={() => enabled && onGo(s.id)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
              active ? 'text-white' : enabled ? 'text-slate-400 hover:text-slate-200' : 'text-slate-600'}`}
            style={active ? { background: 'var(--studio-surface)' } : undefined}>
            <span className="inline-block w-1.5 h-1.5 rounded-full mr-1.5 align-middle"
                  style={{ background: HUES[s.id] }} />
            {s.id} {s.label}
          </button>
        )
      })}
    </div>
  )
}
```

`src/pages/Studio.jsx` (shell only this task; PremiseStage added Task 4):

```jsx
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import StageTabs from '@/components/studio/StageTabs'
import useStudioSync from '@/hooks/useStudioSync'
import { validateStage } from '@/lib/studioState'

export default function Studio() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const { state, patch, ready, saveStatus } = useStudioSync(projectId, (id) =>
    navigate(`/studio/${id}`, { replace: true }))
  const [stage, setStage] = useState(1)
  const [furthest, setFurthest] = useState(1)

  useEffect(() => { if (ready) { setStage(state.stage || 1); setFurthest(state.stage || 1) } }, [ready]) // eslint-disable-line

  if (!ready) return <div className="min-h-screen studio-root flex items-center justify-center text-sm" style={{color:'var(--studio-muted)'}}>Loading…</div>

  const goTo = (n) => {
    if (n > stage) {
      for (let s = stage; s < n; s++) {
        const v = validateStage(state, s)
        if (!v.ok) return // silently refuse; stage components surface errors
      }
    }
    setStage(n); setFurthest(Math.max(furthest, n))
    patch({ stage: n })
  }

  return (
    <div className="studio-root min-h-screen flex flex-col">
      <header className="flex items-center justify-between px-4 h-14 border-b" style={{ borderColor: 'var(--studio-border)' }}>
        <span className="text-sm font-700 tracking-widest" style={{ color: 'var(--studio-text)' }}>
          CONTENT<span style={{ color: 'var(--studio-muted)' }}>WEAVER</span>{' '}
          <span style={{ color: 'var(--studio-accent)' }}>STUDIO</span>
        </span>
        <span className="text-xs" style={{ color: 'var(--studio-muted)' }} role="status">
          {saveStatus === 'saving' ? 'Saving…' : saveStatus === 'saved' ? 'Saved' : ''}
        </span>
      </header>
      <StageTabs current={stage} furthest={furthest} onGo={goTo} />
      <main className="flex-1 overflow-y-auto p-6 max-w-3xl mx-auto w-full">
        {/* Stage components (Tasks 4+, later plans) */}
      </main>
    </div>
  )
}
```

`App.jsx` — add routes (keep everything else):

```jsx
<Route path="/studio" element={<ProtectedRoute><Studio /></ProtectedRoute>} />
<Route path="/studio/:projectId" element={<ProtectedRoute><Studio /></ProtectedRoute>} />
```

- [ ] **Step 4: GREEN** — both test files pass; `npx vite build` ok.

- [ ] **Step 5: Commit** — `feat: studio shell — routes, stage tabs, state contract, gates`

---

### Task 3: api.js studio methods + useStudioSync hook

**Files:**
- Modify: `money_weaver_frontend/src/services/api.js`
- Create: `money_weaver_frontend/src/hooks/useStudioSync.js`
- Test: `money_weaver_frontend/src/__tests__/useStudioSync.test.jsx`

- [ ] **Step 1: Failing test** (mock fetch via existing msw setup in tests; or vi.spyOn(ApiService, ...) — match existing test style in `src/__tests__/`)

```jsx
import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import useStudioSync from '@/hooks/useStudioSync'
import ApiService from '@/services/api'

beforeEach(() => { localStorage.clear(); vi.restoreAllMocks() })

describe('useStudioSync', () => {
  it('creates draft on first use when no projectId, then navigates', async () => {
    const onCreated = vi.fn()
    vi.spyOn(ApiService, 'createStudioProject').mockResolvedValue({ id: 42 })
    const { result } = renderHook(() => useStudioSync(undefined, onCreated))
    await waitFor(() => expect(result.current.ready).toBe(true))
    expect(onCreated).toHaveBeenCalledWith(42)
  })

  it('localStorage immediate, server sync on patch with stage change', async () => {
    vi.spyOn(ApiService, 'getStudioState').mockResolvedValue({ studio_state: null })
    const save = vi.spyOn(ApiService, 'saveStudioState').mockResolvedValue({ saved_at: 'x' })
    const { result } = renderHook(() => useStudioSync(7, () => {}))
    await waitFor(() => expect(result.current.ready).toBe(true))
    act(() => result.current.patch({ premise: { text: 'cats', durationSec: 60, nicheId: '', sequenceProjectId: null } }))
    expect(localStorage.getItem('studio-draft-7')).toContain('cats')
    await act(async () => result.current.patch({ stage: 2 })) // stage flip triggers PUT
    expect(save).toHaveBeenCalled()
    expect(localStorage.getItem('studio-draft-7')).toBeNull()
  })

  it('server state wins on load; localStorage used only when server empty', async () => {
    localStorage.setItem('studio-draft-9', JSON.stringify({ ...{}, premise: { text: 'local' } }))
    vi.spyOn(ApiService, 'getStudioState').mockResolvedValue({ studio_state: { premise: { text: 'server' } } })
    const { result } = renderHook(() => useStudioSync(9, () => {}))
    await waitFor(() => expect(result.current.ready).toBe(true))
    expect(result.current.state.premise.text).toBe('server')
  })
})
```

- [ ] **Step 2: RED** — fails (module missing).

- [ ] **Step 3: Implement**

`api.js` (append to class):

```js
  async createStudioProject() {
    return this.request('/projects/studio', { method: 'POST', body: JSON.stringify({}) })
  }
  async getStudioState(projectId) {
    return this.request(`/projects/${projectId}/studio`)
  }
  async saveStudioState(projectId, state) {
    return this.request(`/projects/${projectId}/studio`, { method: 'PUT', body: JSON.stringify(state) })
  }
  async generateDescription(premise, script = '') {
    return this.request('/generate/description', { method: 'POST', body: JSON.stringify({ premise, script }) })
  }
```

Note: `getStudioState` 404s when no draft — hook must treat 404 item as null, not throw. Implement in hook: wrap in try/catch checking error status.

`src/hooks/useStudioSync.js`:

```js
import { useCallback, useEffect, useRef, useState } from 'react'
import ApiService from '@/services/api'
import { defaultStudioState, SCHEMA_VERSION } from '@/lib/studioState'

const lsKey = (id) => `studio-draft-${id}`
const deepMerge = (base, patch) => {
  const out = { ...base }
  for (const [k, v] of Object.entries(patch || {})) {
    out[k] = v && typeof v === 'object' && !Array.isArray(v)
      ? deepMerge(base?.[k] ?? {}, v)
      : v
  }
  return out
}

export default function useStudioSync(projectId, onCreated = () => {}) {
  const [state, setState] = useState(defaultStudioState())
  const [ready, setReady] = useState(false)
  const [saveStatus, setSaveStatus] = useState('idle')
  const idRef = useRef(projectId ?? null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        if (projectId == null) {
          const p = await ApiService.createStudioProject()
          idRef.current = p.id
          onCreated(p.id)
        } else {
          idRef.current = projectId
          let serverState = null
          try {
            serverState = (await ApiService.getStudioState(projectId))?.studio_state ?? null
          } catch { serverState = null }
          if (serverState) setState({ ...defaultStudioState(), ...serverState })
          else {
            const raw = localStorage.getItem(lsKey(projectId))
            if (raw) setState({ ...defaultStudioState(), ...JSON.parse(raw) })
          }
        }
      } finally {
        if (!cancelled) setReady(true)
      }
    })()
    return () => { cancelled = true }
  }, [projectId]) // eslint-disable-line react-hooks/exhaustive-deps

  const flush = useCallback(async (next) => {
    if (idRef.current == null) return
    setSaveStatus('saving')
    try {
      await ApiService.saveStudioState(idRef.current, { ...next, savedAt: undefined, updatedAt: new Date().toISOString() })
      localStorage.removeItem(lsKey(idRef.current))
      setSaveStatus('saved')
    } catch { setSaveStatus('idle') } // stays in localStorage; resilient
  }, [])

  const patch = useCallback((partial) => {
    setState((prev) => {
      const next = { ...deepMerge(prev, partial), updatedAt: new Date().toISOString() }
      next.schemaVersion = SCHEMA_VERSION
      if (idRef.current != null) localStorage.setItem(lsKey(idRef.current), JSON.stringify(next))
      if (partial.stage) flush(next)       // stage transitions sync to server
      return next
    })
  }, [flush])

  return { state, patch, ready, saveStatus, projectId: idRef.current }
}
```

- [ ] **Step 4: GREEN** — `npx vitest run src/__tests__/useStudioSync.test.jsx` passes.

- [ ] **Step 5: Commit** — `feat: studio sync hook — localStorage instant, server sync at stage transitions`

---

### Task 4: PremiseStage

**Files:**
- Create: `money_weaver_frontend/src/components/studio/PremiseStage.jsx`
- Test: `money_weaver_frontend/src/__tests__/premiseStage.test.jsx`

- [ ] **Step 1: Failing test**

```jsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import PremiseStage from '@/components/studio/PremiseStage'
import ApiService from '@/services/api'

const BASE = {
  premise: { text: '', durationSec: 60, nicheId: '', sequenceProjectId: null },
}

it('suggest fills premise text from random idea', async () => {
  vi.spyOn(ApiService, 'randomIdea').mockResolvedValue({ title: 'Cats', topic: 'A cat learns to code', script: '' })
  const patch = vi.fn()
  render(<PremiseStage state={BASE} patch={patch} />)
  fireEvent.click(screen.getByRole('button', { name: /AI suggest/i }))
  await waitFor(() => expect(patch).toHaveBeenCalled())
  expect(patch.mock.calls[0][0].premise.text).toBe('A cat learns to code')
})

it('discover topics feeds premise via click', async () => {
  vi.spyOn(ApiService, 'fetchTopics').mockResolvedValue({ topics: [{ title: 'AI gardens', source: 'hn', url: '' }] })
  const patch = vi.fn()
  render(<PremiseStage state={{ ...BASE, premise: { ...BASE.premise, nicheId: 'technology' } }} patch={patch} />)
  fireEvent.click(screen.getByRole('button', { name: /AI discover/i }))
  fireEvent.click(await screen.findByText('AI gardens'))
  expect(patch.mock.calls.at(-1)[0].premise.text).toBe('AI gardens')
})

it('exposes duration select with spec values', () => {
  render(<PremiseStage state={BASE} patch={() => {}} />)
  expect(screen.getByRole('option', { name: '60 seconds' })).toBeInTheDocument()
  expect(screen.getByRole('option', { name: '5 minutes' })).toBeInTheDocument()
})
```

- [ ] **Step 2: RED** — fails.

- [ ] **Step 3: Implement** `src/components/studio/PremiseStage.jsx`:

```jsx
import { useState } from 'react'
import AIGenButton from '@/components/studio/AIGenButton'
import ApiService from '@/services/api'
import { DURATIONS } from '@/lib/studioState'

const fmt = (s) => (s % 60 === 0 ? `${s / 60} minute${s > 60 ? 's' : ''}` : `${s} seconds`)

export default function PremiseStage({ state, patch }) {
  const [topics, setTopics] = useState([])
  const p = state.premise
  const setPremise = (updates) => patch({ premise: { ...p, ...updates } })

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-1">
          <label htmlFor="premise" className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>Premise</label>
          <AIGenButton label="suggest" onGenerate={async () => {
            const r = await ApiService.randomIdea({})
            setPremise({ text: r.topic || r.title || '' })
          }} />
        </div>
        <textarea id="premise" rows={3} value={p.text}
          onChange={(e) => setPremise({ text: e.target.value })}
          placeholder="What's the video about?"
          className="w-full rounded-md p-3 text-sm border outline-none focus:ring-1"
          style={{ background: 'var(--studio-surface)', borderColor: 'var(--studio-border)', color: 'var(--studio-text)' }} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="duration" className="block text-xs font-semibold tracking-widest uppercase mb-1" style={{ color: 'var(--studio-muted)' }}>Duration</label>
          <select id="duration" value={p.durationSec}
            onChange={(e) => setPremise({ durationSec: Number(e.target.value) })}
            className="w-full rounded-md p-2.5 text-sm border"
            style={{ background: 'var(--studio-surface)', borderColor: 'var(--studio-border)', color: 'var(--studio-text)' }}>
            {DURATIONS.map((d) => <option key={d} value={d}>{fmt(d)}</option>)}
          </select>
        </div>
        <div>
          <div className="flex items-center justify-between mb-1">
            <label htmlFor="niche" className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>Niche</label>
            <AIGenButton label="discover" disabled={!p.nicheId} onGenerate={async () => {
              const r = await ApiService.fetchTopics(p.nicheId, 20)
              setTopics(r?.topics ?? [])
            }} />
          </div>
          <input id="niche" value={p.nicheId} placeholder="e.g. technology"
            onChange={(e) => setPremise({ nicheId: e.target.value })}
            className="w-full rounded-md p-2.5 text-sm border"
            style={{ background: 'var(--studio-surface)', borderColor: 'var(--studio-border)', color: 'var(--studio-text)' }} />
        </div>
      </div>

      {topics.length > 0 && (
        <div className="space-y-1" role="list">
          {topics.map((t) => (
            <button key={t.title} type="button" onClick={() => setPremise({ text: t.title })}
              className="block w-full text-left text-sm rounded-md px-3 py-2 border hover:border-[var(--studio-accent)] transition-colors"
              style={{ background: 'var(--studio-surface)', borderColor: 'var(--studio-border)', color: 'var(--studio-text)' }}>
              {t.title}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

Note: niche is a free-text input here (sent as `niche_id` — backend validates `[a-z0-9_-]{1,32}`); discovered topics list rendered under it. Wire Stage component into `Studio.jsx` main: `{stage === 1 && <PremiseStage state={state} patch={patch} />}`.

- [ ] **Step 4: GREEN** — `npx vitest run` full suite passes.

- [ ] **Step 5: Commit** — `feat: PremiseStage — premise+duration+niche discovery wired to state`

---

### Task 5: S2 close-out

- [ ] **Step 1:** `npx vitest run` all green; `npx vite build` ok.
- [ ] **Step 2:** Manual smoke: `pnpm dev`, open `/studio`, type premise, see "Saved" indicator, reload — state persists via server once stage advances; localStorage before that.
- [ ] **Step 3:** progress.md line + commit `chore: studio S2 shell+premise close-out` + push.
