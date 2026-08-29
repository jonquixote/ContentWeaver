import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import StoryboardStage from '@/components/studio/StoryboardStage'
import ApiService from '@/services/api'

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
    expect(screen.getByText(/Opening/)).toBeInTheDocument()
  })

  it('visual-text edit writes into overrides', () => {
    const patch = vi.fn()
    render(<StoryboardStage state={BASE} patch={patch} />)
    fireEvent.change(screen.getAllByPlaceholderText(/visual/i)[0], {
      target: { value: 'close up of fluffy cat' },
    })
    expect(patch.mock.calls.at(-1)[0].storyboard.overrides['1'].visualText).toBe(
      'close up of fluffy cat',
    )
  })

  it('reads overrides on load (visualText shown)', () => {
    const state = { ...BASE, storyboard: { overrides: { '2': { visualText: 'smoke moment' } } } }
    render(<StoryboardStage state={state} patch={() => {}} />)
    const inputs = screen.getAllByPlaceholderText(/visual/i)
    expect(inputs[1].value).toBe('smoke moment')
  })

  it('duration edit feeds overrides and updates total chip', () => {
    const patch = vi.fn()
    const { rerender } = render(<StoryboardStage state={BASE} patch={patch} />)
    fireEvent.change(screen.getAllByRole('spinbutton')[0], { target: { value: '7' } })
    expect(patch.mock.calls.at(-1)[0].storyboard.overrides['1'].durationSec).toBe(7)

    const updated = {
      ...BASE,
      storyboard: { overrides: { '1': { durationSec: 7 } } },
    }
    rerender(<StoryboardStage state={updated} patch={patch} />)
    expect(screen.getByTestId('total-duration').textContent).toContain('12s')
  })

  it('suggest fills visual text from enhance-prompt', async () => {
    vi.spyOn(ApiService, 'enhancePrompt').mockResolvedValue({ enhanced: 'soft lit cat typing' })
    const patch = vi.fn()
    render(<StoryboardStage state={BASE} patch={patch} />)
    fireEvent.click(screen.getAllByRole('button', { name: /AI suggest/i })[0])
    await waitFor(() => expect(patch).toHaveBeenCalled())
    expect(patch.mock.calls.at(-1)[0].storyboard.overrides['1'].visualText).toBe(
      'soft lit cat typing',
    )
  })

  it('image upload stores a data-URL imageKey in overrides', async () => {
    vi.spyOn(FileReader.prototype, 'readAsDataURL').mockImplementation(function () {
      Object.defineProperty(this, 'result', {
        value: 'data:image/png;base64,abc',
        configurable: true,
      })
      if (this.onload) this.onload()
    })
    const patch = vi.fn()
    const { container } = render(<StoryboardStage state={BASE} patch={patch} />)
    const file = new File(['x'], 'ref.png', { type: 'image/png' })
    const input = container.querySelectorAll('input[type=file]')[0]
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(patch).toHaveBeenCalled())
    expect(patch.mock.calls.at(-1)[0].storyboard.overrides['1'].imageKey).toBe(
      'data:image/png;base64,abc',
    )
  })

  it('renders a reference image when an override has an imageKey', () => {
    const state = {
      ...BASE,
      storyboard: { overrides: { '1': { imageKey: 'data:image/png;base64,abc' } } },
    }
    render(<StoryboardStage state={state} patch={() => {}} />)
    expect(screen.getByRole('img')).toHaveAttribute('src', 'data:image/png;base64,abc')
  })
})