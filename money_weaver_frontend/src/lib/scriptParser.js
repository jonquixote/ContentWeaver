const TITLE_PATTERN = /^\s*\**Title:\s*[""]?([^"\n*]+)[""]?\**/im
const NARRATIVE_PATTERN = /\*\*Full Narrative:\*\*\s*(.*?)(?=\n\*\*Scene|\n\*\*$|$)/is
const SCENE_PATTERN =
  /\*\*Scene\s+(\d+):\s*([^(]+)\s*\((\d+)s?-(\d+)s?\)\*\*\s*$(.*?)$\s*Voiceover:\s*[""]?(.*?)(?=[""]?$|$)/gims
const SCENE_LINE_PATTERN = /^\*\*Scene\s+(\d+):\s*([^(\n]+)\s*\((\d+)s?-(\d+)s?\)\*\*(.*)$/i
const VOICEOVER_LINE_PATTERN = /^voiceover:\s*"?([^"]*)"?\s*$/i

export function jsonToScriptText(json) {
  if (!json || !Array.isArray(json.content)) return ''
  return json.content.map(blockToLine).join('\n').trim()
}

function blockToLine(block) {
  if (!Array.isArray(block.content)) return ''
  return block.content.map(inlineToText).join('')
}

function inlineToText(node) {
  if (node.type === 'hardBreak') return '\n'
  if (node.type !== 'text') return ''
  const isBold = Array.isArray(node.marks) && node.marks.some((mark) => mark.type === 'bold')
  const text = node.text ?? ''
  return isBold ? `**${text}**` : text
}

export function parseScriptText(text) {
  const titleMatch = text.match(TITLE_PATTERN)
  const title = titleMatch ? titleMatch[1].trim() : 'Untitled Video'

  const narrativeMatch = text.match(NARRATIVE_PATTERN)
  const fullNarrative = narrativeMatch ? narrativeMatch[1].trim() : ''

  const scenes = []
  let match
  SCENE_PATTERN.lastIndex = 0
  while ((match = SCENE_PATTERN.exec(text)) !== null) {
    const start = parseInt(match[3], 10)
    const end = parseInt(match[4], 10)
    scenes.push({
      scene_number: parseInt(match[1], 10),
      description: match[2].trim(),
      start_time: start,
      end_time: end,
      duration: end - start,
      visual_description: match[5].trim(),
      voiceover: match[6].trim(),
    })
  }

  if (scenes.length === 0) {
    return { title, full_narrative: fullNarrative, scenes: parseFallback(text) }
  }

  return { title, full_narrative: fullNarrative, scenes }
}

function parseFallback(text) {
  const lines = text.split('\n')
  const scenes = []
  let current = null

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    const match = line.match(SCENE_LINE_PATTERN)
    if (!match) continue

    if (current) scenes.push(current)
    const start = parseInt(match[3], 10)
    const end = parseInt(match[4], 10)
    current = {
      scene_number: parseInt(match[1], 10),
      description: match[2].trim(),
      start_time: start,
      end_time: end,
      duration: end - start,
      visual_description: '',
      voiceover: '',
    }

    const sameLine = (match[5] || '').trim()
    if (sameLine) {
      const parenthetical = sameLine.match(/^\((.*)\)$/)
      current.visual_description = parenthetical ? parenthetical[1] : sameLine
    }

    for (let j = i + 1; j < lines.length; j++) {
      const nextLine = lines[j].trim()
      if (VOICEOVER_LINE_PATTERN.test(nextLine)) {
        const voiceMatch = nextLine.match(VOICEOVER_LINE_PATTERN)
        if (voiceMatch) current.voiceover = voiceMatch[1].trim()
        i = j
        break
      }
      if (/^\*\*Scene/i.test(nextLine) || /^\*\*Title/i.test(nextLine)) {
        i = j - 1
        break
      }
      if (nextLine) {
        current.visual_description = current.visual_description
          ? `${current.visual_description} ${nextLine}`
          : nextLine
      }
    }
  }

  if (current) scenes.push(current)
  return scenes
}