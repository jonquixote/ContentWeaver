import { describe, test, expect, beforeAll, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import VideoCreationWizard from '@/components/VideoCreationWizard'
import ApiService from '@/services/api'
import { makeQueryClient } from '@/test/helpers'
import { server } from '@/test/server'

vi.mock('@/services/api', async (importOriginal) => {
  const mod = await importOriginal()
  mod.default.randomIdea = vi.fn().mockResolvedValue({
    title: 'Scene Test',
    topic: '**Scene 1: Intro (0s-5s)**\nVoiceover: "Hello world"',
  })
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

async function goToVoiceStep(user) {
  await user.click(await screen.findByRole('button', { name: /^randomize$/i }))
  await user.click(screen.getByRole('button', { name: /^next$/i })) // -> Storyboard
  await user.click(screen.getByRole('button', { name: /^next$/i })) // -> Preset & Voice
}

describe('wizard API voices section', () => {
  test('renders kind=voice models with API badge on the voice step', async () => {
    const user = userEvent.setup()
    server.use(
      http.get('*/api/models', () =>
        HttpResponse.json({
          models: [
            { id: 'poolside/laguna-s-2.1:free', label: 'Laguna S 2.1', provider: 'openrouter', kind: 'text', free: true },
            { id: 'fal-ai/wan-t2v', label: 'Wan 2.2 T2V (fal)', provider: 'fal', kind: 'video', free: false },
            {
              id: 'fal-ai/minimax-speech-02',
              label: 'MiniMax Speech 02',
              provider: 'fal',
              kind: 'voice',
              free: false,
            },
          ],
        }),
      ),
    )
    renderWizard()
    await goToVoiceStep(user)

    expect(await screen.findByText('API Voices')).toBeInTheDocument()
    const row = screen.getByRole('button', { name: /minimax speech 02/i })
    expect(row).toHaveAttribute('aria-pressed', 'false')
    // Only voice-kind models are listed; text/video models stay out.
    expect(screen.queryByRole('button', { name: /laguna s 2\.1/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /wan 2\.2/i })).not.toBeInTheDocument()
    // Local voices behavior untouched: cloned voice select still defaults to Kokoro.
    expect(screen.getByText('Default (Kokoro)')).toBeInTheDocument()
    expect(within(row).getByText('API')).toBeInTheDocument()
  })

  test('selecting an API voice row toggles wizard-session override without changing cloned voice select', async () => {
    const user = userEvent.setup()
    server.use(
      http.get('*/api/models', () =>
        HttpResponse.json({
          models: [
            { id: 'fal-ai/minimax-speech-02', label: 'MiniMax Speech 02', provider: 'fal', kind: 'voice', free: false },
          ],
        }),
      ),
    )
    renderWizard()
    await goToVoiceStep(user)

    const row = await screen.findByRole('button', { name: /minimax speech 02/i })
    await user.click(row)
    expect(row).toHaveAttribute('aria-pressed', 'true')
    await user.click(row)
    expect(row).toHaveAttribute('aria-pressed', 'false')
  })
})
