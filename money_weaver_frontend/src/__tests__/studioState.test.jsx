import { describe, it, expect } from 'vitest'
import { defaultStudioState, validateStage, SCHEMA_VERSION, sceneCount } from '@/lib/studioState'

describe('studioState', () => {
  it('defaults match S1 contract', () => {
    const s = defaultStudioState()
    expect(s.stage).toBe(1)
    expect(s.schemaVersion).toBe(SCHEMA_VERSION)
    expect(s.premise.durationSec).toBe(60)
    expect(s.render.workflowType).toBe('assembler')
    expect(s.script).toHaveProperty('scriptText')
  })

  it('stage 1 gate requires premise text', () => {
    expect(validateStage(defaultStudioState(), 1).ok).toBe(false)
    const s = defaultStudioState()
    s.premise.text = 'x'
    expect(validateStage(s, 1).ok).toBe(true)
  })

  it('stage 2 gate requires title and a parsed scene', () => {
    const s = defaultStudioState()
    s.premise.text = 'x'
    expect(validateStage(s, 2).ok).toBe(false)
    s.script.title = 'My video'
    expect(validateStage(s, 2).ok).toBe(false)
    s.script.scriptText = '**Scene 1: Intro (0s-5s)**\nVisual\nVoiceover: hello'
    expect(validateStage(s, 2).ok).toBe(true)
  })

  it('stage 4 gate requires preset only when presets exist', () => {
    const s = defaultStudioState()
    expect(validateStage(s, 4, { presets: [] }).ok).toBe(true)
    expect(validateStage(s, 4, { presets: [{ id: 1 }] }).ok).toBe(false)
    s.render.presetId = 1
    expect(validateStage(s, 4, { presets: [{ id: 1 }] }).ok).toBe(true)
  })

  it('sceneCount parses canonical screenplay', () => {
    const s = defaultStudioState()
    s.script.scriptText = '**Scene 1: A (0s-5s)**\nVisual\nVoiceover: x\n**Scene 2: B (5s-10s)**\nVisual\nVoiceover: y'
    expect(sceneCount(s)).toBe(2)
  })
})