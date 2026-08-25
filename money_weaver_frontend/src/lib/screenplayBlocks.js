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
    if (TRANSITIONS.includes(line.toUpperCase())) {
      blocks.push({ type: 'transition', text: line.toUpperCase() }); current = null; continue }
    const c = line.match(CHAR_RE)
    if (c) { current = c[1]; continue }
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
// Scene headers carry ONLY a bold mark — jsonToScriptText's inlineToText
// wraps bold marks in ** itself, so literal asterisks would double-wrap.
export function blockToInsertContent(block) {
  const p = (...texts) => ({ type: 'paragraph', content: texts.flat() })
  const t = (text, bold = false) => text === ''
    ? [] : [{ type: 'text', ...(bold ? { marks: [{ type: 'bold' }] } : {}), text }]
  switch (block.type) {
    case 'sceneHeader': return p(t(`Scene ${block.number || 1}: ${block.name || 'INT. LOCATION - DAY'} (${block.start ?? 0}s-${block.end ?? 5}s)`, true))
    case 'voiceover': return p(t('Voiceover: ""'))
    case 'dialogue': return [p(t(`${(block.character || 'NAME').toUpperCase()}:`)), p(t('[DIALOGUE: ]'))]
    case 'transition': return p(t('CUT TO:'))
    default: return p(t(block.text || ''))
  }
}
