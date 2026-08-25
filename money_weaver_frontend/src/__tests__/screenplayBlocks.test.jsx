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
