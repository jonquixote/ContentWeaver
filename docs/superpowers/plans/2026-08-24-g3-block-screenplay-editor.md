# G3: Block Screenplay Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Block-based screenplay editing in ScriptEditor — draggable + click-to-insert palette, prefilled dual-parser-compatible blocks, character autocomplete — serializing to the `**Scene N (Xs-Ys)**` + `Voiceover:` canon.

**Architecture:** Plain TipTap (no custom node types needed — the canon maps to paragraphs with bold marks for headers, exactly like today's placeholder suggests). A new pure module `src/lib/screenplayBlocks.js` owns block definitions, text→blocks parse, blocks→text serialize, and doc-extraction of character names. ScriptEditor gains a palette bar (HTML5 dragstart + click handlers) and inserts blocks via `editor.commands.insertContentAt`. Serialization stays in `jsonToScriptText`-compatible plain text so `parseScriptText`/storyboard and backend parsing keep working unchanged. Existing external-value sync effect (G2-3) remains the load path; initial empty content becomes sceneHeader+voiceover seed.

**Tech Stack:** TipTap StarterKit (existing dep), HTML5 drag events, vitest/jsdom.

**Repo facts:** Root `/Volumes/JOHNNY DISK/MoneyWeaver`. Frontend dir `money_weaver_frontend`; tests `npx vitest run` (baseline **46**); build `npx vite build`. Files: `src/components/ScriptEditor.jsx` (useEditor at :8, onChange at :12, external sync at :25), `src/lib/scriptParser.js` (`jsonToScriptText` bold-mark serializer at :8-23, `SCENE_LINE_PATTERN`, `VOICEOVER_LINE_PATTERN`), wizard integration via `formData.scriptHtml`.

---

### Task 1: screenplayBlocks.js — block defs, parser, serializer

**Files:**
- Create: `money_weaver_frontend/src/lib/screenplayBlocks.js`
- Test: `money_weaver_frontend/src/__tests__/screenplayBlocks.test.jsx`

- [ ] **Step 1: Failing tests**

```jsx
import { describe, it, expect } from 'vitest'
import {
  BLOCK_TYPES, parseScreenplay, serializeScreenplay,
  extractCharacters, seedBlocks, blockToInsertContent,
} from '@/lib/screenplayBlocks'

const SAMPLE = [
  '**Scene 1: INT. OFFICE - DAY (0s-5s)**',
  'A ham sandwich sits in a drawer.',
  'Voiceover: "It was a normal Tuesday."',
  '',
  '**Scene 2: EXT. STREET - CONTINUOUS (5s-9s)**',
  'CUT TO:',
].join('\n')

describe('screenplayBlocks', () => {
  it('exposes the five palette block types', () => {
    expect(BLOCK_TYPES.map(b => b.type)).toEqual(
      ['sceneHeader', 'voiceover', 'visual', 'dialogue', 'transition'])
  })

  it('parses canonical text into typed blocks', () => {
    const blocks = parseScreenplay(SAMPLE)
    expect(blocks[0]).toMatchObject({ type: 'sceneHeader', number: 1,
      name: 'INT. OFFICE - DAY', start: 0, end: 5 })
    expect(blocks[1]).toMatchObject({ type: 'visual' })
    expect(blocks[2]).toMatchObject({ type: 'voiceover',
      text: 'It was a normal Tuesday.' })
    expect(blocks.at(-1)).toMatchObject({ type: 'transition', text: 'CUT TO:' })
  })

  it('round-trips blocks -> text -> same blocks', () => {
    const blocks = parseScreenplay(SAMPLE)
    const text = serializeScreenplay(blocks)
    expect(parseScreenplay(text)).toEqual(blocks)
    expect(text).toContain('**Scene 1: INT. OFFICE - DAY (0s-5s)**')
    expect(text).toContain('Voiceover: "It was a normal Tuesday."')
  })

  it('serializes dialogue with CHARACTER line and [DIALOGUE:]', () => {
    const text = serializeScreenplay([
      { type: 'sceneHeader', number: 1, name: 'INT. BAR - NIGHT', start: 0, end: 4 },
      { type: 'dialogue', character: 'SAM', text: 'Hello?' },
    ])
    expect(text).toContain('SAM:')
    expect(text).toContain('[DIALOGUE: Hello?]')
  })

  it('extractCharacters returns distinct uppercase names', () => {
    const blocks = [
      { type: 'dialogue', character: 'Sam', text: 'x' },
      { type: 'dialogue', character: 'SAM', text: 'y' },
      { type: 'voiceover', text: 'z' },
    ]
    expect(extractCharacters(blocks)).toEqual(['SAM'])
  })

  it('seedBlocks gives sceneHeader+voiceover defaults', () => {
    const seeded = seedBlocks()
    expect(seeded.map(b => b.type)).toEqual(['sceneHeader', 'voiceover'])
    expect(seeded[0].number).toBe(1)
  })

  it('blockToInsertContent builds tiptap JSON per type', () => {
    const c = blockToInsertContent({ type: 'voiceover', text: '' })
    expect(c.type).toBe('paragraph')
    expect(JSON.stringify(c)).toContain('Voiceover:')
  })
})
```

- [ ] **Step 2: RED**
- [ ] **Step 3: Implement**

```js
// src/lib/screenplayBlocks.js
const HEADER_RE = /^\*\*Scene\s+(\d+):\s*([^(\n]+?)\s*\((\d+)s?-(\d+)s?\)\*\*\s*$/i
const VO_RE = /^Voiceover:\s*"?(.*?)"?\s*$/i
const DLG_RE = /^\[DIALOGUE:\s*(.*?)\]\s*$/i
const CHAR_RE = /^([A-Z][A-Z0-9 \-]{0,30}):\s*$/
export const TRANSITIONS = ['CUT TO:', 'MATCH CUT TO:', 'FADE OUT.', 'SMASH CUT TO:']

export const BLOCK_TYPES = [
  { type: 'sceneHeader', label: 'Scene Header' },
  { type: 'voiceover', label: 'Voiceover' },
  { type: 'visual', label: 'Visual / Action' },
  { type: 'dialogue', label: 'Dialogue' },
  { type: 'transition', label: 'Transition' },
]

export function parseScreenplay(text) {
  const blocks = []
  let current = null // pending dialogue character
  for (const raw of String(text || '').split('\n')) {
    const line = raw.trim()
    if (!line) { current = null; continue }
    const h = line.match(HEADER_RE)
    if (h) {
      blocks.push({ type: 'sceneHeader', number: +h[1], name: h[2].trim(),
        start: +h[3], end: +h[4] }); continue
    }
    const vo = line.match(VO_RE)
    if (vo) { blocks.push({ type: 'voiceover', text: vo[1] }); current = null; continue }
    const d = line.match(DLG_RE)
    if (d) { blocks.push({ type: 'dialogue', character: current || '', text: d[1] }); continue }
    const c = line.match(CHAR_RE)
    if (c) { current = c[1]; continue }
    if (TRANSITIONS.includes(line.toUpperCase())) {
      blocks.push({ type: 'transition', text: line.toUpperCase() }); current = null; continue }
    blocks.push({ type: 'visual', text: line }); current = null
  }
  return blocks
}

function esc(s) { return String(s ?? '').replace(/"/g, "'") }

export function serializeScreenplay(blocks) {
  const out = []
  for (const b of blocks || []) {
    if (b.type === 'sceneHeader')
      out.push(`**Scene ${b.number}: ${b.name} (${b.start}s-${b.end}s)**`)
    else if (b.type === 'voiceover') out.push(`Voiceover: "${esc(b.text)}"`)
    else if (b.type === 'visual') out.push(b.text)
    else if (b.type === 'dialogue') {
      if (b.character) out.push(`${b.character.toUpperCase()}:`)
      out.push(`[DIALOGUE: ${esc(b.text)}]`)
    } else if (b.type === 'transition') out.push(b.text)
  }
  return out.filter(l => l !== '').join('\n').trim()
}

export function extractCharacters(blocks) {
  return [...new Set((blocks || [])
    .filter(b => b.type === 'dialogue' && b.character)
    .map(b => b.character.toUpperCase()))]
}

export function seedBlocks() {
  return [
    { type: 'sceneHeader', number: 1, name: 'INT. LOCATION - DAY', start: 0, end: 5 },
    { type: 'voiceover', text: '' },
  ]
}

export function renumber(blocks) {
  let n = 0
  return (blocks || []).map(b => b.type === 'sceneHeader'
    ? { ...b, number: ++n } : b)
}

// Build a TipTap insertContent payload (paragraph(s)) for one block.
export function blockToInsertContent(block) {
  const p = (...texts) => ({ type: 'paragraph', content: texts })
  const t = (text, bold = false) => text === ''
    ? [] : [{ type: 'text', ...(bold ? { marks: [{ type: 'bold' }] } : {}), text }]
  switch (block.type) {
    case 'sceneHeader': return p(t(`**Scene ${block.number || 1}: ${block.name || 'INT. LOCATION - DAY'} (${block.start ?? 0}s-${block.end ?? 5}s)**`, true))
    case 'voiceover': return p(t('Voiceover: ""'))
    case 'dialogue': return [p(t(`${(block.character || 'NAME').toUpperCase()}:`)), p(t('[DIALOGUE: ]'))]
    case 'transition': return p(t('CUT TO:'))
    default: return p(t(block.text || ''))
  }
}
```

Note: header prefill uses literal `**...**` text inside bold mark intentionally — serialized text
keeps asterisks via inlineToText's bold handling; verify round-trip test covers this and adjust
mark/text split if jsonToScriptText double-wraps (** inside bold yields `****`). If double-wrap
occurs, drop the literal asterisks and rely on the bold mark alone.

- [ ] **Step 4: GREEN → Commit** `feat: screenplay block model — parse/serialize/seed/insert`

---

### Task 2: ScriptEditor palette + insertion + autocomplete

**Files:**
- Modify: `money_weaver_frontend/src/components/ScriptEditor.jsx`
- Modify: `money_weaver_frontend/src/lib/screenplayBlocks.js` (only if insertion helpers needed)
- Test: `money_weaver_frontend/src/__tests__/scriptEditorPalette.test.jsx`

- [ ] **Step 1: Failing tests**

```jsx
import { render, screen, fireEvent } from '@testing-library/react'
import ScriptEditor from '@/components/ScriptEditor'
import { vi } from 'vitest'

// jsdom has no TipTap DOM geometry — mock minimal editor surface like existing
// wizardGenerative tests do for ScriptEditor (read that file first; reuse its mocks).
test('palette renders five chips', () => {
  render(<ScriptEditor value="" onChange={() => {}} />)
  expect(screen.getByRole('button', { name: /scene header/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /voiceover/i })).toBeInTheDocument()
  expect(screen.getAllByRole('button', { name: /dialogue/i }).length).toBeGreaterThan(0)
})

test('click chip inserts block content and emits change', () => {
  const onChange = vi.fn()
  render(<ScriptEditor value="" onChange={onChange} />)
  fireEvent.click(screen.getByRole('button', { name: /voiceover/i }))
  // onChange fired with html containing Voiceover marker
  const lastCall = onChange.mock.calls.at(-1)
  expect(lastCall[1]).toContain('Voiceover:')
})

test('chips are draggable', () => {
  render(<ScriptEditor value="" onChange={() => {}} />)
  const chip = screen.getByRole('button', { name: /transition/i })
  expect(chip.getAttribute('draggable')).toBe('true')
  expect(chip.dataset.blockType).toBe('transition')
})
```

Read `wizardGenerative.test.jsx` FIRST — G2-3 already mocks ScriptEditor internals there;
reuse its exact editor-mock approach so jsdom doesn't need real ProseMirror.

- [ ] **Step 2: RED**
- [ ] **Step 3: Implement** in ScriptEditor.jsx:
  - Palette row above EditorContent: chips from BLOCK_TYPES; each `<button draggable data-block-type onDragStart={e=>e.dataTransfer.setData('text/block-type', b.type)} onClick={insertAfterCurrent}>`.
  - Click insert: `editor.commands.insertContentAt(editor.state.selection.to, blockToInsertContent(block))` then focus; onChange fires via existing onUpdate.
  - Drop support: wrapper div `onDragOver={e=>e.preventDefault()}` + `onDrop` reading `text/block-type`, computing pos via `editor.view.posAtCoords({left, top})`, insertContentAt(pos).
  - After any structural insert: renumber scene headers by reading back `serializeScreenplay(jsonToScriptText-ish)` — simplest: keep numbers stable except when inserting sceneHeader (assign next number).
  - Empty-editor seed: in the existing init effect, if value empty → setContent from seedBlocks serialization.
  - Character autocomplete: defer to polish if time-boxed; minimum viable = datalist-style hint chip showing extracted characters under palette (non-blocking v1) — implement `extractCharacters` display only.
- [ ] **Step 4: GREEN + full vitest + build**
- [ ] **Step 5: Commit** `feat: script editor palette — draggable/clickable block insertion`

---

### Task 3: Wizard round-trip + storyboard compatibility

**Files:**
- Modify: `money_weaver_frontend/src/components/VideoCreationWizard.jsx` (draft-script conversion uses serializeScreenplay; storyboard step unchanged)
- Test: extend `src/__tests__/wizardGenerative.test.jsx`

- [ ] **Step 1: Failing test**

```jsx
test('draft script output parses into storyboard scenes', async () => {
  // msw scripts/draft returns canonical SAMPLE-format screenplay (Task 1 format)
  // click Draft Script (accept overwrite confirm)
  // proceed to step 2 requires scenes.length > 0 — assert storyboard step renders
  // at least one scene card (query by scene description text from the draft)
})
```

- [ ] **Step 2: RED → Fix `scriptTextToHtml` in wizard to delegate to
`serializeScreenplay(parseScreenplay(scriptText))` then wrap lines as before (bold-header rule
now matches HEADER_RE output). Remove the ad-hoc converter. GREEN.**
- [ ] **Step 3: Full vitest + build**
- [ ] **Step 4: Commit** `feat: draft script feeds block editor and storyboard round-trip`

---

### Task 4: G3 close-out

- [ ] Full frontend ≥49 green; build ok; backend suite untouched-green spot check.
- [ ] Live smoke: boot servers; probe user; open wizard; insert each block type; verify storyboard step shows scenes from inserted blocks.
- [ ] Update `.superpowers/sdd/progress.md`; push contentweaver main.
