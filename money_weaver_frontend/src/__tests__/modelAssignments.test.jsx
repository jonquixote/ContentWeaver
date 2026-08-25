import { describe, test, expect, beforeAll, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { Toaster } from 'sonner'
import SettingsPage from '@/components/SettingsPage'
import { makeQueryClient } from '@/test/helpers'
import { server } from '@/test/server'

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

function renderSettings() {
  const qc = makeQueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <div>
          <SettingsPage />
          <Toaster />
        </div>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('model assignments card', () => {
  test('loads saved assignment into the idea picker', async () => {
    server.use(
      http.get('*/api/model-assignments', () =>
        HttpResponse.json({ assignments: { idea: 'poolside/laguna-s-2.1:free' } })),
    )
    renderSettings()
    expect(await screen.findByText(/model assignments/i)).toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: /laguna s 2\.1/i }),
    ).toBeInTheDocument()
  })

  test('voice picker offers the local chain option', async () => {
    const user = userEvent.setup()
    renderSettings()
    await screen.findByText(/model assignments/i)
    const pickers = screen.getAllByRole('button', { name: /select a model/i })
    await user.click(pickers[3]) // Voice TTS row
    expect(await screen.findByText(/local chain \(auto\)/i)).toBeInTheDocument()
  })

  test('save assignments PUTs values and shows success toast', async () => {
    const user = userEvent.setup()
    let putBody = null
    server.use(
      http.put('*/api/model-assignments', async ({ request }) => {
        putBody = await request.json()
        return HttpResponse.json({ ok: true })
      }),
    )
    renderSettings()
    await screen.findByText(/model assignments/i)
    const pickers = screen.getAllByRole('button', { name: /select a model/i })
    await user.click(pickers[0]) // Idea Generation row
    await user.click(await screen.findByText(/nemotron lightning/i))
    await user.click(screen.getByRole('button', { name: /save assignments/i }))
    await waitFor(() => expect(screen.getByText(/saved successfully/i)).toBeTruthy())
    expect(putBody).toEqual({
      assignments: { idea: 'nvidia/nemotron-3.5-lightning:free' },
    })
  })
})
