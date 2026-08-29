import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import RenderStage from '@/components/studio/RenderStage'

vi.mock('@/hooks/usePresets', () => ({
  usePresets: () => ({
    data: [{ id: 2, name: 'Shorts', platform: 'shorts', width: 1080, height: 1920, fps: 30, duration_min: 15, duration_max: 60 }],
  }),
}))
vi.mock('@/hooks/useVoices', () => ({
  useVoices: () => ({ data: [{ id: 3, name: 'Clone-1' }] }),
}))
vi.mock('@/hooks/useModels', () => ({
  useModels: () => ({ data: { models: [{ id: 'fal-ai/tts', label: 'Fal Voice', kind: 'voice', provider: 'fal' }] } }),
}))
vi.mock('@/components/ModelPicker', () => ({
  default: ({ value, onChange, kinds }) => (
    <select
      aria-label={kinds.join(',')}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value || null)}
    >
      <option value="">Auto</option>
      <option value="m1">M1</option>
    </select>
  ),
}))

const BASE = {
  script: { title: 'Cat', description: '', scriptHtml: '', scriptText: 'x', characters: [] },
  render: {
    presetId: null,
    voiceType: 'female',
    voiceId: null,
    voiceModelOverride: null,
    textModelOverride: null,
    workflowType: 'assembler',
    orientation: 'landscape',
    width: '1920',
    height: '1080',
    language: 'en',
  },
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

  it('text model override picker writes textModelOverride', () => {
    const patch = vi.fn()
    render(<RenderStage state={BASE} patch={patch} />)
    fireEvent.change(screen.getByRole('combobox', { name: 'text' }), { target: { value: 'm1' } })
    expect(patch.mock.calls.at(-1)[0].render.textModelOverride).toBe('m1')
  })
})