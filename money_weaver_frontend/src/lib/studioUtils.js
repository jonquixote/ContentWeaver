import { parseScreenplay, serializeScreenplay } from './screenplayBlocks'

// Plain script text -> editor HTML. Draft output is normalized to the
// **Scene N (Xs-Ys)** + Voiceover: canon first (dual-parser fix shipped 2026-08-27).
export const scriptTextToHtml = (text) => {
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
  return serializeScreenplay(parseScreenplay(text))
    .split('\n')
    .map((line) =>
      /^\*\*.*\*\*$/.test(line)
        ? `<p><strong>${esc(line.slice(2, -2))}</strong></p>`
        : `<p>${esc(line)}</p>`,
    )
    .join('')
}