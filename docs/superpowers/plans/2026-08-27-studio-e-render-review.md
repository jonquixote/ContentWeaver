# Studio S5: Render + Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stage 4 (workflow, preset, voice, model overrides) and Stage 5 (summary + create video + progress tracker).

**Architecture:** `RenderStage.jsx` — workflow radio, preset select (`usePresets`), voice (built-in / cloned via `useVoices` / fal API voices via `useModels` filtered `kind='voice'`), inline model overrides (`ModelPicker` component). `ReviewStage.jsx` — summary of stages 1-4 + Create → `ApiService.createProject` (or reuse the draft project!) → `generateAssemblerVideo` / `generateGenerativeVideo` → `VideoProgressTracker` modal.

**Tech Stack:** React, existing hooks `usePresets/useVoices/useModels`, `ModelPicker`, `VideoProgressTracker`, vitest.

**Spec:** `docs/superpowers/specs/2026-08-27-studio-flow-design.md` · **Depends:** S4.

**Important:** draft project already exists (created by sync hook) — Create should reuse `projectId` from sync hook (passed via Studio), NOT spawn a duplicate. `Project.workflow_type` set per render config.

---

### Task 1: RenderStage

**Files:**
- Create: `money_weaver_frontend/src/components/studio/RenderStage.jsx`
- Test: `money_weaver_frontend/src/__tests__/renderStage.test.jsx`

- [ ] **Step 1: Failing tests**

```jsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import RenderStage from '@/components/studio/RenderStage'

vi.mock('@/hooks/usePresets', () => ({ usePresets: () => ({ data: [{ id: 2, name: 'Shorts', platform: 'shorts', width: 1080, height: 1920, fps: 30, duration_min: 15, duration_max: 60 }] }) }))
vi.mock('@/hooks/useVoices', () => ({ useVoices: () => ({ data: [{ id: 3, name: 'Clone-1' }] }) }))
vi.mock('@/hooks/useModels', () => ({ useModels: () => ({ data: { models: [{ id: 'fal-ai/tts', label: 'Fal Voice', kind: 'voice', provider: 'fal' }] } }) }))
vi.mock('@/components/ModelPicker', () => ({ default: ({ value, onChange, kinds }) => <select aria-label={kinds.join(',')} value={value ?? ''} onChange={(e) => onChange(e.target.value || null)}><option value="">Auto</option><option value="m1">M1</option></select> }))

const BASE = {
  script: { title: 'Cat', description: '', scriptHtml: '', scriptText: 'x', characters: [] },
  render: { presetId: null, voiceType: 'female', voiceId: null, voiceModelOverride: null,
           workflowType: 'assembler', orientation: 'landscape', width: '1920', height: '1080', language: 'en' },
}

describe('RenderStage', () => {
  it('preset select applies orientation/dims', () => {
    const patch = vi.fn()
    render(<RenderStage state={BASE} patch={patch} />)
    fireEvent.change(screen.getByLabelText(/preset/i), { target: { value: '2' } })
    const upd = patch.mock.calls.at(-1)[0].render
    expect(upd.presetId).toBe(2)
    expect(upd.orientation).toBe('portrait')
    expect(upd.width).toBe('1080')
  })

  it('fal API voice toggles voiceModelOverride', () => {
    const patch = vi.fn()
    render(<RenderStage state={BASE} patch={patch} />)
    const btn = screen.getByRole('button', { name: /fal voice/i })
    fireEvent.click(btn)
    expect(patch.mock.calls.at(-1)[0].render.voiceModelOverride).toBe('fal-ai/tts')
  })

  it('workflow radio switches', () => {
    const patch = vi.fn()
    render(<RenderStage state={BASE} patch={patch} />)
    fireEvent.click(screen.getByLabelText(/generative/i))
    expect(patch.mock.calls.at(-1)[0].render.workflowType).toBe('generative')
  })
})
```

- [ ] **Step 2: RED** — fails.

- [ ] **Step 3: Implement** `src/components/studio/RenderStage.jsx`:

```jsx
import ModelPicker from '@/components/ModelPicker'
import { useModels } from '@/hooks/useModels'
import { usePresets } from '@/hooks/usePresets'
import { useVoices } from '@/hooks/useVoices'

const inputStyle = { background: 'var(--studio-surface)', borderColor: 'var(--studio-border)', color: 'var(--studio-text)' }
const sectionLabel = 'text-xs font-semibold tracking-widest uppercase'

export default function RenderStage({ state, patch }) {
  const r = state.render
  const setRender = (updates) => patch({ render: { ...r, ...updates } })
  const presets = usePresets().data ?? []
  const voices = useVoices().data ?? []
  const apiVoices = (useModels().data?.models ?? []).filter((m) => m?.kind === 'voice')

  return (
    <div className="space-y-6">
      <div>
        <label className={sectionLabel} style={{ color: 'var(--studio-muted)' }}>Workflow</label>
        <div role="radiogroup" className="flex gap-4 mt-2">
          {['assembler', 'generative'].map((w) => (
            <label key={w} className="flex items-center gap-2 text-sm" style={{ color: 'var(--studio-text)' }}>
              <input type="radio" name="workflow" value={w} checked={r.workflowType === w}
                onChange={() => setRender({ workflowType: w })} /> {w}
            </label>
          ))}
        </div>
      </div>

      <div>
        <label htmlFor="preset" className={sectionLabel} style={{ color: 'var(--studio-muted)' }}>Preset</label>
        <select id="preset" value={r.presetId ?? ''} onChange={(e) => {
          const preset = presets.find((p) => p.id === Number(e.target.value)) || null
          if (!preset) return setRender({ presetId: null })
          setRender({
            presetId: preset.id,
            width: String(preset.width), height: String(preset.height),
            orientation: preset.width > preset.height ? 'landscape' : preset.width < preset.height ? 'portrait' : 'square',
          })
        }} className="w-full mt-2 rounded-md p-2.5 text-sm border" style={{ ...inputStyle, borderColor: 'var(--studio-border)' }}>
          <option value="">Select a preset…</option>
          {presets.map((p) => <option key={p.id} value={p.id}>{p.name} — {p.width}x{p.height}</option>)}
        </select>
      </div>

      <div>
        <label htmlFor="voiceType" className={sectionLabel} style={{ color: 'var(--studio-muted)' }}>Voice type</label>
        <select id="voiceType" value={r.voiceType} onChange={(e) => setRender({ voiceType: e.target.value })}
          className="w-full mt-2 rounded-md p-2.5 text-sm border" style={{ ...inputStyle, borderColor: 'var(--studio-border)' }}>
          {['female', 'male', 'neutral'].map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
      </div>

      <div>
        <label className={sectionLabel} style={{ color: 'var(--studio-muted)' }}>Cloned voice</label>
        <select value={r.voiceId ?? 'default'} onChange={(e) => setRender({ voiceId: e.target.value === 'default' ? null : Number(e.target.value) })}
          className="w-full mt-2 rounded-md p-2.5 text-sm border" style={{ ...inputStyle, borderColor: 'var(--studio-border)' }}>
          <option value="default">Default (chain)</option>
          {voices.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
        </select>
      </div>

      {apiVoices.length > 0 && (
        <div>
          <label className={sectionLabel} style={{ color: 'var(--studio-muted)' }}>API voices</label>
          <div className="grid gap-2 mt-2">
            {apiVoices.map((m) => (
              <button key={m.id} type="button"
                aria-pressed={r.voiceModelOverride === m.id}
                onClick={() => setRender({ voiceModelOverride: r.voiceModelOverride === m.id ? null : m.id })}
                className="text-left px-3 py-2 rounded-md border text-sm"
                style={{ borderColor: r.voiceModelOverride === m.id ? 'var(--studio-accent)' : 'var(--studio-border)', color: 'var(--studio-text)' }}>
                {m.label || m.display_name || m.id}
                {m.provider && <span className="text-xs block" style={{ color: 'var(--studio-muted)' }}>{m.provider}</span>}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={sectionLabel} style={{ color: 'var(--studio-muted)' }}>Text model override</label>
          <ModelPicker models={useModels().data?.models ?? []} value={null} onChange={null}
            kinds={['text']} compact />
        </div>
        <div>
          <label className={sectionLabel} style={{ color: 'var(--studio-muted)' }}>Language</label>
          <select value={r.language} onChange={(e) => setRender({ language: e.target.value })}
            className="w-full mt-2 rounded-md p-2.5 text-sm border" style={{ ...inputStyle, borderColor: 'var(--studio-border)' }}>
            {['en', 'es', 'fr', 'de', 'zh'].map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
      </div>
    </div>
  )
}
```

(ModelPicker override wiring: pass real models + setter; the test mocks it. `kinds=['text']`.)

- [ ] **Step 4: GREEN** — tests pass.

- [ ] **Step 5: Commit** — `feat: RenderStage — workflow/preset/voice/model overrides`

---

### Task 2: ReviewStage + Create flow

**Files:**
- Create: `money_weaver_frontend/src/components/studio/ReviewStage.jsx`
- Modify: `money_weaver_frontend/src/pages/Studio.jsx` (wire 3/4/5 + pass projectId from sync hook)
- Test: `money_weaver_frontend/src/__tests__/reviewStage.test.jsx`

- [ ] **Step 1: Failing tests**

```jsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ReviewStage from '@/components/studio/ReviewStage'
import ApiService from '@/services/api'

const BASE = {
  premise: { text: 'cats code', durationSec: 60, nicheId: 'technology', sequenceProjectId: null },
  script: { title: 'Cats', description: 'desc', scriptHtml: '<p>x</p>', scriptText: '**Scene 1: A (0s-5s)**\nfoo\nVoiceover: "v"', characters: [] },
  storyboard: { overrides: {} },
  render: { presetId: 2, voiceType: 'female', voiceId: null, voiceModelOverride: null,
           workflowType: 'assembler', orientation: 'portrait', width: '1080', height: '1920', language: 'en' },
}

it('create enqueues assembler on existing project id and starts tracker', async () => {
  const enq = vi.spyOn(ApiService, 'generateAssemblerVideo').mockResolvedValue({ task_id: 't-1' })
  render(<ReviewStage state={BASE} projectId={9} />)
  fireEvent.click(screen.getByRole('button', { name: /create video/i }))
  await screen.findByText(/progress|video/i, { selector: 'div, span' })
  expect(enq).toHaveBeenCalledTimes(1)
  expect(enq.mock.calls[0][0]).toBe(9) // existing draft project, no duplicate create
  expect(enq.mock.calls[0][1]).toBe(BASE.script.scriptText)
})
```

Simpler assertion: called once with projectId=9; tracker shows when task id set.

- [ ] **Step 2: RED** — fails.

- [ ] **Step 3: Implement** `src/components/studio/ReviewStage.jsx`:

```jsx
import { useState } from 'react'
import { useAuthStore } from '@/store/authStore'
import ApiService from '@/services/api'
import VideoProgressTracker from '@/components/VideoProgressTracker'
import { parseScriptText } from '@/lib/scriptParser'
import { toast } from 'sonner'

export default function ReviewStage({ state, projectId, onDone }) {
  const [taskId, setTaskId] = useState(null)
  const [busy, setBusy] = useState(false)
  const r = state.render
  const { scenes } = parseScriptText(state.script.scriptText || '')

  const create = async () => {
    const user = useAuthStore.getState().user
    if (!user?.id || projectId == null) {
      toast.error('Not ready — draft project missing')
      return
    }
    setBusy(true)
    try {
      const opts = {
        voice_type: r.voiceType, voice_id: r.voiceId,
        voice_override: r.voiceModelOverride || undefined,
        duration: Number(state.premise.durationSec),
        orientation: r.orientation, width: Number(r.width), height: Number(r.height),
      }
      const resp = r.workflowType === 'generative'
        ? await ApiService.generateGenerativeVideo(projectId, state.script.scriptText, { voice_id: r.voiceId })
        : await ApiService.generateAssemblerVideo(projectId, state.script.scriptText, opts)
      setTaskId(resp.task_id)
    } catch (e) {
      toast.error(e?.message || 'Failed to start video creation')
      setBusy(false)
    }
  }

  if (taskId) {
    return <VideoProgressTracker taskId={taskId} onClose={() => { setTaskId(null); onDone?.() }} />
  }

  return (
    <div className="space-y-4">
      <div className="rounded-md p-4 border" style={{ borderColor: 'var(--studio-border)', background: 'var(--studio-card)' }}>
        <h3 className="text-sm font-medium mb-2" style={{ color: 'var(--studio-text)' }}>{state.script.title || 'Untitled'}</h3>
        <p className="text-sm" style={{ color: 'var(--studio-muted)' }}>{state.premise.text}</p>
        {state.script.description && <p className="text-sm mt-1" style={{ color: 'var(--studio-muted)' }}>{state.script.description}</p>}
      </div>
      <div className="rounded-md p-4 border" style={{ borderColor: 'var(--studio-border)', background: 'var(--studio-card)' }}>
        <div className="grid grid-cols-2 gap-2 text-sm" style={{ color: 'var(--studio-text)' }}>
          <span>Scenes: {scenes.length}</span>
          <span>Workflow: {r.workflowType}</span>
          <span>Preset: {r.presetId ?? 'none'}</span>
          <span>Voice: {r.voiceType}{r.voiceId ? ` + clone #${r.voiceId}` : ''}{r.voiceModelOverride ? ' (API voice)' : ''}</span>
          <span>Resolution: {r.width}x{r.height}</span>
          <span>Language: {r.language}</span>
        </div>
      </div>
      <p className="text-xs" style={{ color: 'var(--studio-muted)' }}>
        Estimated processing time: {r.workflowType === 'generative' ? '5-15 min' : '2-5 min'}
      </p>
      <button type="button" disabled={busy} onClick={create}
        className="px-5 py-2 rounded-md text-sm font-semibold" style={{ background: 'var(--studio-accent)', color: '#06262b' }}>
        {busy ? 'Creating…' : 'Create video'}
      </button>
    </div>
  )
}
```

`Studio.jsx` wiring (replace main block):

```jsx
{stage === 1 && <PremiseStage state={state} patch={patch} />}
{stage === 2 && <ScriptStage state={state} patch={patch} />}
{stage === 3 && <StoryboardStage state={state} patch={patch} />}
{stage === 4 && <RenderStage state={state} patch={patch} />}
{stage === 5 && <ReviewStage state={state} projectId={syncProjectId} onDone={reset-or-back} />}
```

(Store `projectId` via `useStudioSync`'s return `projectId`.)

- [ ] **Step 4: GREEN** — `npx vitest run` passes.

- [ ] **Step 5: Commit** — `feat: ReviewStage — summary + create + tracker`

---

### Task 3: S5 close-out

- [ ] **Step 1:** `npx vitest run` green; `npx vite build` ok.
- [ ] **Step 2:** Manual: full 5-stage pass with enqueue mocked (or 503 grace without redis) — tracker renders when queue available, graceful toast otherwise.
- [ ] **Step 3:** progress.md; commit `chore: studio S5 render+review close-out`; push.
