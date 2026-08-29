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
      presetId: null,
      voiceType: 'female',
      voiceId: null,
      voiceModelOverride: null,
      workflowType: 'assembler',
      orientation: 'landscape',
      width: '1920',
      height: '1080',
      language: 'en',
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
      return {
        ok: t(state.premise?.text) !== '',
        errors: t(state.premise?.text) ? [] : ['Premise required'],
      }
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