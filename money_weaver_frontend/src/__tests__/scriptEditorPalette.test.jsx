import { render, screen, fireEvent } from '@testing-library/react'
import ScriptEditor from '@/components/ScriptEditor'
import { vi } from 'vitest'

// jsdom has no TipTap DOM geometry, but basic commands work: the existing
// wizardGenerative tests render this same real ScriptEditor successfully.
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
  // onChange fired with script text containing Voiceover marker
  const lastCall = onChange.mock.calls.at(-1)
  expect(lastCall[1]).toContain('Voiceover:')
})

test('chips are draggable', () => {
  render(<ScriptEditor value="" onChange={() => {}} />)
  const chip = screen.getByRole('button', { name: /transition/i })
  expect(chip.getAttribute('draggable')).toBe('true')
  expect(chip.dataset.blockType).toBe('transition')
})
