import { describe, test, expect, beforeAll, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import VideoCreationWizard from '@/components/VideoCreationWizard'
import ApiService from '@/services/api'
import { makeQueryClient } from '@/test/helpers'
import { server } from '@/test/server'

vi.mock('@/services/api', async (importOriginal) => {
  const mod = await importOriginal()
  mod.default.randomIdea = vi.fn().mockResolvedValue({ title: 'Random Title', topic: 'Random topic' })
  return mod
})

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

beforeEach(() => {
  vi.mocked(ApiService.randomIdea).mockClear()
})

afterEach(() => {
  cleanup()
})

function renderWizard() {
  const qc = makeQueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <VideoCreationWizard onBack={() => {}} />
    </QueryClientProvider>,
  )
}

describe('wizard inline model overrides', () => {
  test('collapsed by default; expanding reveals Idea model and Script model pickers', async () => {
    const user = userEvent.setup()
    renderWizard()
    const toggle = await screen.findByRole('button', { name: /advanced: model overrides/i })
    expect(screen.queryByText('Idea model')).not.toBeInTheDocument()
    await user.click(toggle)
    expect(screen.getByText('Idea model')).toBeInTheDocument()
    expect(screen.getByText('Script model')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /select a model/i })).toHaveLength(2)
  })

  test('pickers are pre-seeded with saved assignments', async () => {
    const user = userEvent.setup()
    server.use(
      http.get('*/api/model-assignments', () =>
        HttpResponse.json({
          assignments: { idea: 'poolside/laguna-s-2.1:free', script: 'nvidia/nemotron-3.5-lightning:free' },
        }),
      ),
    )
    renderWizard()
    await user.click(await screen.findByRole('button', { name: /advanced: model overrides/i }))
    const seeded = screen.getAllByRole('button', { name: /laguna s 2\.1|nemotron lightning/i })
    expect(seeded).toHaveLength(2)
  })

  test('choosing an idea override passes model into randomIdea payload', async () => {
    const user = userEvent.setup()
    renderWizard()
    await user.click(await screen.findByRole('button', { name: /advanced: model overrides/i }))
    const pickers = screen.getAllByRole('button', { name: /select a model/i })
    await user.click(pickers[0])
    await user.click(await screen.findByText(/nemotron lightning/i))
    await user.click(screen.getByRole('button', { name: /^randomize$/i }))
    await waitFor(() =>
      expect(ApiService.randomIdea).toHaveBeenCalledWith({ model: 'nvidia/nemotron-3.5-lightning:free' }),
    )
  })

  test('randomize without overrides sends an empty payload', async () => {
    const user = userEvent.setup()
    renderWizard()
    await screen.findByRole('button', { name: /advanced: model overrides/i })
    await user.click(screen.getByRole('button', { name: /^randomize$/i }))
    await waitFor(() => expect(ApiService.randomIdea).toHaveBeenCalledWith({}))
  })
})
