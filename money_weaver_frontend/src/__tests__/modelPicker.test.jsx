import { describe, test, expect, beforeAll, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ModelPicker from '@/components/ModelPicker'

// Radix Select needs pointer-capture APIs jsdom does not implement.
beforeAll(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn()
  window.HTMLElement.prototype.hasPointerCapture = vi.fn()
  window.HTMLElement.prototype.releasePointerCapture = vi.fn()
  window.HTMLElement.prototype.setPointerCapture = vi.fn()
  if (!window.PointerEvent) {
    window.PointerEvent = class PointerEvent extends MouseEvent {}
  }
})

const MODELS = [
  { id: 'poolside/laguna-s-2.1:free', label: 'Laguna S 2.1', provider: 'openrouter', kind: 'text', free: true },
  { id: 'fal-ai/wan-t2v', label: 'Wan 2.2 T2V (fal)', provider: 'fal', kind: 'video', free: false },
  { id: 'nvidia/nemotron-3.5-lightning:free', label: 'Nemotron Lightning', provider: 'openrouter', kind: 'text', free: true },
]

function setup(props = {}) {
  return render(<ModelPicker models={MODELS} value={null} onChange={() => {}} {...props} />)
}

describe('model picker', () => {
  test('renders search box and provider chips when opened', async () => {
    const user = userEvent.setup()
    setup()
    await user.click(screen.getByRole('button', { name: /select a model/i }))
    expect(screen.getByPlaceholderText(/search models/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'openrouter' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'fal' })).toBeInTheDocument()
  })

  test('search filters case-insensitively by id and label', async () => {
    const user = userEvent.setup()
    setup({ value: null })
    await user.click(screen.getByRole('button', { name: /select a model/i }))
    await user.type(screen.getByPlaceholderText(/search models/i), 'laguna')
    expect(await screen.findByText(/laguna s 2\.1/i)).toBeInTheDocument()
    expect(screen.queryByText(/wan 2\.2/i)).not.toBeInTheDocument()
  })

  test('clicking an option calls onChange with the model id and closes panel', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    setup({ onChange })
    await user.click(screen.getByRole('button', { name: /select a model/i }))
    await user.click(await screen.findByText(/wan 2\.2/i))
    expect(onChange).toHaveBeenCalledWith('fal-ai/wan-t2v')
    expect(screen.queryByPlaceholderText(/search models/i)).not.toBeInTheDocument()
  })

  test('kinds prop pre-filters options and provider chips', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<ModelPicker models={MODELS} value={null} onChange={onChange} kinds={['video']} />)
    await user.click(screen.getByRole('button', { name: /select a model/i }))
    expect(await screen.findByText(/wan 2\.2/i)).toBeInTheDocument()
    expect(screen.queryByText(/laguna/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'fal' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'openrouter' })).not.toBeInTheDocument()
  })

  test('free models sort first and show Free badge with provider suffix', async () => {
    const user = userEvent.setup()
    setup()
    await user.click(screen.getByRole('button', { name: /select a model/i }))
    const list = await screen.findByRole('listbox')
    const items = [...list.querySelectorAll('[role="option"]')]
    const labels = items.map((el) => el.textContent)
    expect(labels[0]).toMatch(/laguna s 2\.1/i)
    expect(labels).toEqual([
      expect.stringMatching(/laguna/i),
      expect.stringMatching(/nemotron/i),
      expect.stringMatching(/wan/i),
    ])
    expect(labels[0]).toMatch(/· openrouter/i)
  })
})
