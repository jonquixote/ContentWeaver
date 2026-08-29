# Studio S4: Storyboard Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stage 3 — scene cards parsed from script, per-scene editable visual description (+AI suggest), optional reference image upload, editable scene durations, live total-duration chip.

**Architecture:** `StoryboardStage.jsx` reads `state.script.scriptText` through `parseScriptText` (existing `src/lib/scriptParser.js`) → scene cards. Edits write to `state.storyboard.overrides[sceneNumber]` = `{ visualText, imageKey, durationSec }`. Suggest reuses `/api/enhance-prompt`. Image upload reuses existing presign flow (`ApiService.presignUpload` → `putUpload`). Total duration = sum of per-scene (override.durationSec ?? scene.duration).

**Tech Stack:** React, existing `scriptParser.js`, `api.js`, vitest.

**Spec:** `docs/superpowers/specs/2026-08-27-studio-flow-design.md` · **Depends:** S3 (script stage), uploads router.

**Gate context:** plan B’s `validateStage(3)` checks scenes exist; preset min/max checks happen in stage render (presets fetched — reuse `usePresets` hook returns list). Save override durations directly.

---

### Task 1: Scene cards from script + overrides

**Files:**
- Create: `money_weaver_frontend/src/components/studio/StoryboardStage.jsx`
- Test: `money_weaver_frontend/src/__tests__/storyboardStage.test.jsx`

- [ ] **Step 1: Failing tests**

```jsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import StoryboardStage from '@/components/studio/StoryboardStage'

const SCRIPT_TEXT = [
  '**Scene 1: Opening (0s-5s)**',
  'cat at desk',
  'Voiceover: "The cat codes."',
  '**Scene 2: Ship It (5s-10s)**',
  'deploy button',
  'Voiceover: "It works."',
].join('\n')

const BASE = {
  script: { title: 'Cat', description: '', scriptHtml: '', scriptText: SCRIPT_TEXT, characters: [] },
  storyboard: { overrides: {} },
}

describe('StoryboardStage', () => {
  it('renders one card per parsed scene', () => {
    render(<StoryboardStage state={BASE} patch={() => {}} />)
    expect(screen.getAllByTestId(/scene-card/)).toHaveLength(2)
    expect(screen.getByText('Opening')).toBeInTheDocument()
  })

  it('visual-text edit writes into overrides', () => {
    const patch = vi.fn()
    render(<StoryboardStage state={BASE} patch={patch} />)
    fireEvent.change(screen.getAllByPlaceholderText(/visual/i)[0], { target: { value: 'close up of fluffy cat' } })
    expect(patch.mock.calls.at(-1)[0].storyboard.overrides['1'].visualText)
      .toBe('close up of fluffy cat')
  })

  it('reads overrides on load (visualText shown)', () => {
    const state = { ...BASE, storyboard: { overrides: { '2': { visualText: 'smoke moment' } } } }
    render(<StoryboardStage state={state} patch={() => {}} />)
    const inputs = screen.getAllByPlaceholderText(/visual/i)
    expect(inputs[1].value).toBe('smoke moment')
  })
})
```

- [ ] **Step 2: RED** — fails.

- [ ] **Step 3: Implement** `src/components/studio/StoryboardStage.jsx`:

```jsx
import AIGenButton from '@/components/studio/AIGenButton'
import { parseScriptText } from '@/lib/scriptParser'
import ApiService from '@/services/api'

const inputStyle = { background: 'var(--studio-surface)', borderColor: 'var(--studio-border)', color: 'var(--studio-text)' }

export default function StoryboardStage({ state, patch }) {
  const { scenes } = parseScriptText(state.script?.scriptText || '')
  const overrides = state.storyboard?.overrides || {}

  const setOverride = (sceneNumber, updates) =>
    patch({ storyboard: { overrides: { ...overrides, [sceneNumber]: { ...overrides[sceneNumber], ...updates } } } })

  const total = scenes.reduce((sum, s) => sum + (overrides[s.scene_number]?.durationSec ?? s.duration), 0)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>Storyboard</span>
        <span className="text-xs px-2 py-1 rounded" style={{ background: 'var(--studio-surface)', border: '1px solid var(--studio-border)', color: 'var(--studio-text)' }} data-testid="total-duration">
          {scenes.length} scene{scenes.length === 1 ? '' : 's'} · {total}s
        </span>
      </div>

      {scenes.map((scene) => {
        const ov = overrides[scene.scene_number] || {}
        return (
          <div key={scene.scene_number} data-testid={`scene-card-${scene.scene_number}`}
            className="rounded-md p-4 border" style={{ borderColor: 'var(--studio-border)', background: 'var(--studio-card)' }}>
            <div className="flex items-center justify-between mb-2">
              <h5 className="text-sm font-medium" style={{ color: 'var(--studio-text)' }}>
                Scene {scene.scene_number}: {scene.description}
              </h5>
              <span className="text-xs" style={{ color: 'var(--studio-muted)' }}>
                {ov.durationSec ?? scene.duration}s
              </span>
            </div>

            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>Visual</label>
              <AIGenButton label="suggest" onGenerate={async () => {
                const r = await ApiService.enhancePrompt(
                  `Scene ${scene.scene_number} (${scene.description}): vivid visual for stock/AI video. Script: ${state.script.scriptText}`
                )
                setOverride(scene.scene_number, { visualText: (r.enhanced || '').trim() })
              }} />
            </div>
            <textarea rows={2} value={ov.visualText ?? scene.visual_description}
              placeholder="visual description"
              onChange={(e) => setOverride(scene.scene_number, { visualText: e.target.value })}
              className="w-full rounded-md p-2 text-sm border" style={{ ...inputStyle, borderColor: 'var(--studio-border)' }} />

            {/* duration + image wired in Task 2 */}
            {scene.voiceover && (
              <p className="text-sm mt-2" style={{ color: 'var(--studio-muted)' }}>“{scene.voiceover}”</p>
            )}
          </div>
        )
      })}
    </div>
  )
}
```

Why scenes appear even on odd formats: the parser dual-format fix from the earlier bug is what makes these cards reliable — do NOT regress it in tests.

- [ ] **Step 4: GREEN** — `npx vitest run src/__tests__/storyboardStage.test.jsx` passes.

- [ ] **Step 5: Commit** — `feat: StoryboardStage — scene cards + visual overrides`

---

### Task 2: Duration editing + image upload

**Files:**
- Modify: `money_weaver_frontend/src/components/studio/StoryboardStage.jsx`
- Test: extend `storyboardStage.test.jsx`

- [ ] **Step 1: Failing tests**

```jsx
it('duration edit feeds overrides and updates total chip', () => {
  const patch = vi.fn()
  const { rerender } = render(<StoryboardStage state={BASE} patch={patch} />)
  fireEvent.change(screen.getAllByRole('spinbutton')[0], { target: { value: '7' } })
  expect(patch.mock.calls.at(-1)[0].storyboard.overrides['1'].durationSec).toBe(7)
})

it('image upload stores imageKey in overrides', async () => {
  vi.spyOn(ApiService, 'presignUpload').mockResolvedValue({ upload_url: '/up', key: 'img/x.png' })
  vi.spyOn(ApiService, 'putUpload').mockResolvedValue({})
  const patch = vi.fn()
  const { container } = render(<StoryboardStage state={BASE} patch={patch} />)
  const file = new File(['x'], 'ref.png', { type: 'image/png' })
  fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [file] } })
  await screen.findByRole('img')
  expect(patch.mock.calls.at(-1)[0].storyboard.overrides['1'].imageKey).toBe('img/x.png')
})
```

- [ ] **Step 2: RED** — fails.

- [ ] **Step 3: Implement** — in each scene card, add under the visual textarea:

```jsx
<div className="flex items-center gap-3 mt-2">
  <label className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>Duration</label>
  <input type="number" min={1} max={120}
    value={ov.durationSec ?? scene.duration}
    onChange={(e) => setOverride(scene.scene_number, { durationSec: Number(e.target.value) })}
    className="w-20 rounded-md p-1.5 text-sm border" style={{ ...inputStyle, borderColor: 'var(--studio-border)' }} />
  <label className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>Reference image</label>
  <input type="file" accept="image/*" className="text-xs" style={{ color: 'var(--studio-muted)' }}
    onChange={async (e) => {
      const file = e.target.files?.[0]
      if (!file) return
      const pre = await ApiService.presignUpload(file.name.split('.').pop())
      await ApiService.putUpload(pre.upload_url, file, file.type)
      setOverride(scene.scene_number, { imageKey: pre.key })
    }} />
  {ov.imageKey && (
    <img alt="reference" className="h-10 w-10 rounded object-cover border"
         style={{ borderColor: 'var(--studio-border)' }}
         src={ApiService.getAuthedAssetUrl(ov.imageKey)} />
  )}
</div>
```

Note `ApiService.getAuthedAssetUrl` already exists (used for voice assets). `presignUpload(ext)` response: inspect fields `{upload_url, key}` — if backend returns `key`/`path` under different name, map accordingly in one place (api.js handles it consistently for the whole app; mimic voice-cloning usage).

- [ ] **Step 4: GREEN** — tests pass.

- [ ] **Step 5: Commit** — `feat: StoryboardStage durations + reference image upload`

---

### Task 3: Gate quality + Studio integration

**Files:**
- Modify: `money_weaver_frontend/src/pages/Studio.jsx`

- [ ] **Step 1:** Wire stage into shell: `{stage === 3 && <StoryboardStage state={state} patch={patch} />}`.

- [ ] **Step 2:** Preset-aware duration gate (optional polish): when `render.presetId` set and presets loaded, warn (non-blocking) if total duration outside `duration_min..max` — compute where selectedPreset available (reuse `usePresets`). Simple inline hint row.

- [ ] **Step 3:** `npx vitest run` green; `npx vite build` ok.

- [ ] **Step 4: Commit** — `feat: wire StoryboardStage into Studio`

---

### Task 4: S4 close-out

- [ ] **Step 1:** Full `npx vitest run` green.
- [ ] **Step 2:** Manual: /studio → script with scenes → storyboard lists cards; adjust durations, suggest visual (503 grace without key), upload image → totally persists.
- [ ] **Step 3:** progress.md; commit `chore: studio S4 storyboard close-out`; push.
