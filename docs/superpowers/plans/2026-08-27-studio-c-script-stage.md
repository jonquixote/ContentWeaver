# Studio S3: Script Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stage 2 — title/description AI generation, block script editor with draft/enhance (enhance = improve-only), characters list.

**Architecture:** `ScriptStage.jsx` composes: title input + AIGenButton, description textarea + AIGenButton (new `/api/generate/description`), existing `ScriptEditor` (unchanged), characters panel (auto `extractCharacters` from script text + manual add/remove). Draft path: `/api/scripts/draft` → `scriptTextToHtml(script)` (same helper shape as today's wizard) → editor; `scriptText` stored for gates/storyboard. Enhance path: only when script non-empty, always confirm before overwrite.

**Tech Stack:** React, existing `src/components/ScriptEditor.jsx`, `src/services/api.js`, vitest.

**Spec:** `docs/superpowers/specs/2026-08-27-studio-flow-design.md` · **Depends:** S2 (shell, sync, `state.script`).

**Contract delta to remember:** script state = `script: { title, description, scriptHtml, scriptText, characters[].{name, traits[]} }`. Characters traits are free strings; MVP list only.

---

### Task 1: ScriptStage skeleton + title/description AI buttons

**Files:**
- Create: `money_weaver_frontend/src/components/studio/ScriptStage.jsx`
- Test: `money_weaver_frontend/src/__tests__/scriptStage.test.jsx`

- [ ] **Step 1: Failing tests**

```jsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ScriptStage from '@/components/studio/ScriptStage'
import ApiService from '@/services/api'

vi.mock('@/components/ScriptEditor', () => ({
  default: () => <div data-testid="script-editor" />,
}))

const BASE = {
  premise: { text: 'A cat learns to code', durationSec: 60, nicheId: 'technology', sequenceProjectId: null },
  script: { title: '', description: '', scriptHtml: '', scriptText: '', characters: [] },
}

describe('ScriptStage', () => {
  it('title ✦ sets title from premise via enhance-prompt', async () => {
    vi.spyOn(ApiService, 'enhancePrompt').mockResolvedValue({ enhanced: 'Cat Codes!' })
    const patch = vi.fn()
    render(<ScriptStage state={BASE} patch={patch} />)
    fireEvent.click(screen.getByRole('button', { name: /AI title/i }))
    await waitFor(() => expect(patch).toHaveBeenCalled())
    expect(patch.mock.calls.at(-1)[0].script.title).toBe('Cat Codes!')
  })

  it('description ✦ calls /generate/description with premise+script', async () => {
    const spy = vi.spyOn(ApiService, 'generateDescription').mockResolvedValue({ description: 'A cat joins a team.' })
    const patch = vi.fn()
    render(<ScriptStage state={{ ...BASE, script: { ...BASE.script, scriptText: 'SCENE…' } }} patch={patch} />)
    fireEvent.click(screen.getByRole('button', { name: /AI description/i }))
    await waitFor(() => expect(spy).toHaveBeenCalledWith('A cat learns to code', 'SCENE…'))
    expect(patch.mock.calls.at(-1)[0].script.description).toContain('cat joins')
  })
})
```

- [ ] **Step 2: RED** — `npx vitest run src/__tests__/scriptStage.test.jsx` fails (module missing).

- [ ] **Step 3: Implement** `src/components/studio/ScriptStage.jsx`:

```jsx
import ScriptEditor from '@/components/ScriptEditor'
import AIGenButton from '@/components/studio/AIGenButton'
import ApiService from '@/services/api'
import { toast } from 'sonner'

const inputCls = 'w-full rounded-md p-2.5 text-sm border'
const inputStyle = { background: 'var(--studio-surface)', borderColor: 'var(--studio-border)', color: 'var(--studio-text)' }

export default function ScriptStage({ state, patch }) {
  const s = state.script
  const setScript = (updates) => patch({ script: { ...s, ...updates } })

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-1">
          <label htmlFor="script-title" className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>Title</label>
          <AIGenButton label="title" disabled={!state.premise.text.trim()} onGenerate={async () => {
            const r = await ApiService.enhancePrompt(`${state.premise.text} — write a punchy video title (6-10 words, title case)`)
            setScript({ title: (r.enhanced || '').trim() })
          }} />
        </div>
        <input id="script-title" value={s.title} onChange={(e) => setScript({ title: e.target.value })}
          className={inputCls} style={inputStyle} placeholder="Video title" />
      </div>

      <div>
        <div className="flex items-center justify-between mb-1">
          <label htmlFor="script-desc" className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>Description</label>
          <AIGenButton label="description" disabled={!state.premise.text.trim()} onGenerate={async () => {
            const r = await ApiService.generateDescription(state.premise.text, s.scriptText)
            setScript({ description: (r.description || '').trim() })
          }} />
        </div>
        <textarea id="script-desc" rows={2} value={s.description} onChange={(e) => setScript({ description: e.target.value })}
          className={inputCls} style={inputStyle} placeholder="Shown on the video platform / project card" />
      </div>

      {/* Script editor + characters filled by Tasks 2 and 3 */}
      <ScriptEditor
        value={s.scriptHtml}
        onChange={(html, text) => { /* Task 2 replaces with draft-aware handler */ setScript({ scriptHtml: html, scriptText: text }) }}
      />
    </div>
  )
}
```

Wire into `src/pages/Studio.jsx`: `{stage === 2 && <ScriptStage state={state} patch={patch} />}`.

- [ ] **Step 4: GREEN** — tests pass.

- [ ] **Step 5: Commit** — `feat: ScriptStage — title/description AI generate buttons`

---

### Task 2: Draft script into editor (blocked-behind confirm) + improve-only Enhance

**Files:**
- Modify: `money_weaver_frontend/src/components/studio/ScriptStage.jsx`
- Modify: `money_weaver_frontend/src/lib/studioUtils.js` (new shared helper `scriptTextToHtml`) — create it
- Test: **Extend** `scriptStage.test.jsx`

- [ ] **Step 1: Failing tests**

```jsx
it('draft fills editor with canonical screenplay (storyboard-safe)', async () => {
  const draftText = '**Scene 1: Opening (0s-5s)**\ncat at desk\nVoiceover: "The cat codes."\n'
  vi.spyOn(ApiService, 'draftScript').mockResolvedValue({ script: draftText })
  const patch = vi.fn()
  render(<ScriptStage state={BASE} patch={patch} />)
  fireEvent.click(screen.getByRole('button', { name: /AI draft/i }))
  await waitFor(() => expect(patch).toHaveBeenCalled())
  const upd = patch.mock.calls.at(-1)[0].script
  expect(upd.scriptText).toContain('Voiceover:')
  expect(upd.scriptHtml).toContain('<strong>Scene 1: Opening (0s-5s)</strong>')
})

it('enhance is disabled with empty script (improve-only)', () => {
  render(<ScriptStage state={BASE} patch={() => {}} />)
  expect(screen.getByRole('button', { name: /AI enhance/i })).toBeDisabled()
})

it('draft asks before overwriting existing script', async () => {
  const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
  vi.spyOn(ApiService, 'draftScript').mockResolvedValue({ script: 'x' })
  const patch = vi.fn()
  render(<ScriptStage state={{ ...BASE, script: { ...BASE.script, scriptText: 'existing', scriptHtml: '<p>x</p>' } }} patch={patch} />)
  fireEvent.click(screen.getByRole('button', { name: /AI draft/i }))
  await waitFor(() => expect(confirmSpy).toHaveBeenCalled())
  expect(patch).not.toHaveBeenCalled()
  confirmSpy.mockRestore()
})
```

- [ ] **Step 2: RED** — fails.

- [ ] **Step 3: Implement**

`src/lib/studioUtils.js` (shared; mirrors proven wizard path):

```js
import { parseScreenplay, serializeScreenplay } from './screenplayBlocks'

// Plain script text -> editor HTML. Draft output is normalized to the
// **Scene N (Xs-Ys)** + Voiceover: canon first (dual-parser fix shipped 2026-08-27).
export const scriptTextToHtml = (text) => {
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
  return serializeScreenplay(parseScreenplay(text))
    .split('\n')
    .map((line) => /^\*\*.*\*\*$/.test(line)
      ? `<p><strong>${esc(line.slice(2, -2))}</strong></p>`
      : `<p>${esc(line)}</p>`)
    .join('')
}
```

In `ScriptStage.jsx`, add above the ScriptEditor block:

```jsx
const hasScript = Boolean(s.scriptText.trim())

const handleDraft = async () => {
  if (hasScript && !window.confirm('Replace the current script with a generated draft?')) return
  const r = await ApiService.draftScript({
    topic: state.premise.text,
    duration: state.premise.durationSec,
    niche_id: state.premise.nicheId || undefined,
  })
  const text = r?.script ?? ''
  setScript({ scriptHtml: scriptTextToHtml(text), scriptText: text })
}

const handleEnhance = async () => {
  const r = await ApiService.enhancePrompt(s.scriptText)
  const text = (r.enhanced || '').trim()
  if (!text) return
  if (!window.confirm('Replace script with the enhanced version?')) return
  setScript({ scriptHtml: scriptTextToHtml(text), scriptText: text })
}
```

Render as a toolbar row directly above `<ScriptEditor>`:

```jsx
<div className="flex items-center gap-3">
  <span className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>Script</span>
  <AIGenButton label="draft" disabled={!state.premise.text.trim()} onGenerate={handleDraft} />
  <AIGenButton label="enhance" disabled={!hasScript} onGenerate={handleEnhance} />
</div>
```

- [ ] **Step 4: GREEN** — `npx vitest run src/__tests__/scriptStage.test.jsx` passes.

- [ ] **Step 5: Commit** — `feat: ScriptStage draft (canonicalized) + improve-only enhance`

---

### Task 3: Characters panel

**Files:**
- Modify: `money_weaver_frontend/src/components/studio/ScriptStage.jsx`
- Test: extend `scriptStage.test.jsx`

Requirements: list from `extractCharacters(parseScreenplay(scriptText))` merged with manual entries; manual add (name input + button), delete; store manual additions in `script.characters` (auto-extracted names shown but NOT persisted until edited — keeps state small).

- [ ] **Step 1: Failing tests**

```jsx
it('auto-extracts dialogue characters from script text', () => {
  const scriptText = '**Scene 1: A (0s-5s)**\nJANE:\n[DIALOGUE: Hi]\nVoiceover: "x"'
  render(<ScriptStage state={{ ...BASE, script: { ...BASE.script, scriptText } }} patch={() => {}} />)
  expect(screen.getByText('JANE')).toBeInTheDocument()
})

it('adds manual character to state', () => {
  const patch = vi.fn()
  render(<ScriptStage state={BASE} patch={patch} />)
  fireEvent.change(screen.getByPlaceholderText(/character name/i), { target: { value: 'MILO' } })
  fireEvent.click(screen.getByRole('button', { name: /add character/i }))
  expect(patch.mock.calls.at(-1)[0].script.characters).toEqual([{ name: 'MILO', traits: [] }])
})
```

- [ ] **Step 2: RED** — fails.

- [ ] **Step 3: Implement** — append to `ScriptStage.jsx`:

```jsx
import { useState } from 'react'
import { parseScreenplay, extractCharacters } from '@/lib/screenplayBlocks'
import { X } from 'lucide-react'

// inside component:
const [charName, setCharName] = useState('')
const autoChars = extractCharacters(s.scriptText ? parseScreenplay(s.scriptText) : [])
const manual = (s.characters || []).map((c) => c.name.toUpperCase())
const merged = [...new Set([...autoChars, ...manual])].sort()

const addChar = () => {
  const name = charName.trim().toUpperCase()
  if (!name) return
  setScript({ characters: [...(s.characters || []), { name, traits: [] }] })
  setCharName('')
}
const removeChar = (name) =>
  setScript({ characters: (s.characters || []).filter((c) => c.name.toUpperCase() !== name) })

// render (below ScriptEditor):
<div>
  <span className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>Characters</span>
  <div className="flex flex-wrap gap-2 mt-2">
    {merged.map((name) => (
      <span key={name} className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded"
            style={{ background: 'var(--studio-surface)', border: '1px solid var(--studio-border)', color: 'var(--studio-text)' }}>
        {name}
        {manual.includes(name) && (
          <button type="button" aria-label={`remove ${name}`} onClick={() => removeChar(name)}
                  className="text-slate-500 hover:text-red-400"><X size={12} /></button>
        )}
      </span>
    ))}
  </div>
  <div className="flex gap-2 mt-2">
    <input value={charName} onChange={(e) => setCharName(e.target.value)}
      placeholder="Character name" className={inputCls + ' flex-1'} style={inputStyle} />
    <button type="button" onClick={addChar} aria-label="add character"
      className="px-3 py-1.5 text-xs rounded-md" style={{ background: 'var(--studio-surface)', border: '1px solid var(--studio-border)', color: 'var(--studio-text)' }}>
      Add
    </button>
  </div>
</div>
```

- [ ] **Step 4: GREEN** — full `npx vitest run` passes.

- [ ] **Step 5: Commit** — `feat: ScriptStage characters — auto-extract + manual add/remove`

---

### Task 4: S3 close-out

- [ ] **Step 1:** Full `npx vitest run` green; `npx vite build` ok.
- [ ] **Step 2:** Smoke: `pnpm dev` → /studio → premise → next → draft script → editor populates → Next gate passes (scenes parsed — the 2026-08-27 dual-parser fix means no "no scenes" failure).
- [ ] **Step 3:** progress.md line; commit `chore: studio S3 script stage close-out`; push.
