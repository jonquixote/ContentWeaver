import { describe, test, expect, beforeAll, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import VideoCreationWizard from '@/components/VideoCreationWizard'
import { makeQueryClient } from '@/test/helpers'

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

function renderWizard() {
  const qc = makeQueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <VideoCreationWizard onBack={() => {}} />
    </QueryClientProvider>,
  )
}

describe('niche picker', () => {
  test('shows the niche select with loaded niches', async () => {
    const user = userEvent.setup()
    renderWizard()
    expect(await screen.findByText('Niche')).toBeInTheDocument()
    await user.click(screen.getByRole('combobox'))
    expect(await screen.findByText('personal_finance')).toBeInTheDocument()
    expect(screen.getByText('fitness')).toBeInTheDocument()
  })

  test('selecting a niche enables topic discovery', async () => {
    const user = userEvent.setup()
    renderWizard()
    await screen.findByText('Niche')
    const discover = screen.getByRole('button', { name: /discover topics/i })
    expect(discover).toBeDisabled()
    await user.click(screen.getByRole('combobox'))
    await user.click(await screen.findByText('personal_finance'))
    expect(discover).toBeEnabled()
  })
})
