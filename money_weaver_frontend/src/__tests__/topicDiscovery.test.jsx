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

async function selectNicheAndDiscover(user) {
  await user.click(await screen.findByRole('combobox'))
  await user.click(await screen.findByText('personal_finance'))
  await user.click(screen.getByRole('button', { name: /discover topics/i }))
}

describe('topic discovery', () => {
  test('discover topics shows topic cards from the API', async () => {
    const user = userEvent.setup()
    renderWizard()
    await selectNicheAndDiscover(user)
    expect(await screen.findByText('How to budget on a low income')).toBeInTheDocument()
    expect(screen.getByText('Emergency fund basics')).toBeInTheDocument()
  })

  test('clicking a topic prefills the title field', async () => {
    const user = userEvent.setup()
    renderWizard()
    await selectNicheAndDiscover(user)
    await user.click(await screen.findByText('How to budget on a low income'))
    expect(screen.getByLabelText('Project Title')).toHaveValue('How to budget on a low income')
  })
})
