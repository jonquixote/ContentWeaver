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
  vi.restoreAllMocks()
})

function renderWizard() {
  const qc = makeQueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <VideoCreationWizard onBack={() => {}} />
    </QueryClientProvider>,
  )
}

// Seeds title + prompt through the existing Randomize path so both new
// buttons are enabled without typing into the TipTap editor.
async function seedTopic(user) {
  await user.click(await screen.findByRole('button', { name: /^randomize$/i }))
}

describe('wizard generative tools', () => {
  test('enhance wand replaces prompt text', async () => {
    const user = userEvent.setup()
    server.use(
      http.post('*/api/enhance-prompt', () =>
        HttpResponse.json({ enhanced: 'IMPROVED PROMPT' })),
    )
    renderWizard()
    await seedTopic(user)
    const enhance = await screen.findByRole('button', { name: /enhance prompt/i })
    expect(enhance).toBeEnabled()
    await user.click(enhance)
    // handleScriptChange syncs editor html + prompt: enhanced text lands in the editor.
    const paragraph = await screen.findByText(/improved prompt/i)
    expect(paragraph.closest('[contenteditable]')).not.toBeNull()
  })

  test('draft script fills editor via script assignment', async () => {
    const user = userEvent.setup()
    let draftPayload
    server.use(
      http.post('*/api/scripts/draft', async ({ request }) => {
        draftPayload = await request.json()
        return HttpResponse.json({ script: '**Scene 1: Intro**\nVoiceover: "hello"' })
      }),
    )
    renderWizard()
    await seedTopic(user)
    const draft = await screen.findByRole('button', { name: /draft script/i })
    expect(draft).toBeEnabled()
    await user.click(draft)
    const sceneHeader = await screen.findByText(/scene 1/i)
    // Bold **Scene N** lines become <strong> paragraphs in the editor.
    expect(sceneHeader.closest('strong')).not.toBeNull()
    expect(screen.getByText(/voiceover: "hello"/i)).toBeInTheDocument()
    await waitFor(() =>
      expect(draftPayload).toEqual({ topic: 'Random topic', duration: 30 }),
    )
  })

  test('draft script is disabled until a topic exists', async () => {
    renderWizard()
    expect(await screen.findByRole('button', { name: /draft script/i })).toBeDisabled()
  })

  test('drafting over an existing script confirms before replacing', async () => {
    const user = userEvent.setup()
    let calls = 0
    server.use(
      http.post('*/api/scripts/draft', () => {
        calls += 1
        return HttpResponse.json({ script: '**Scene 9: End**\nVoiceover: "bye"' })
      }),
    )
    renderWizard()
    await seedTopic(user)
    const draft = await screen.findByRole('button', { name: /draft script/i })

    // First draft fills the empty editor (no confirmation needed).
    await user.click(draft)
    await screen.findByText(/scene 9/i)

    // Second draft over non-empty script asks first; declining keeps content.
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => false)
    await user.click(draft)
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringMatching(/replace/i))
    expect(calls).toBe(1)
    expect(screen.getByText(/scene 9/i)).toBeInTheDocument()

    // Accepting proceeds with the replacement request.
    confirmSpy.mockImplementation(() => true)
    await user.click(draft)
    await waitFor(() => expect(calls).toBe(2))
  })

  test('draft script output parses into storyboard scenes', async () => {
    const user = userEvent.setup()
    // Near-canonical draft: the unquoted voiceover must be canonized to
    // `Voiceover: "..."` by serializeScreenplay(parseScreenplay(...)) before
    // it reaches the block editor.
    const DRAFT_SCRIPT = [
      '**Scene 1: INT. OFFICE - DAY (0s-5s)**',
      'A ham sandwich sits in a drawer.',
      'Voiceover: It was a normal Tuesday.',
      '',
      '**Scene 2: EXT. STREET - CONTINUOUS (5s-9s)**',
      'SAM:',
      '[DIALOGUE: Give me the sandwich]',
    ].join('\n')
    server.use(
      http.post('*/api/scripts/draft', () =>
        HttpResponse.json({ script: DRAFT_SCRIPT })),
    )
    renderWizard()
    await seedTopic(user)
    const draft = await screen.findByRole('button', { name: /draft script/i })

    // First draft fills the empty editor without confirmation.
    await user.click(draft)
    await screen.findByText(/scene 1/i)

    // Overwrite confirm accepted; draft lands in the editor.
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    await user.click(draft)
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringMatching(/replace/i))

    // Canon round-trip: serializer restored the Voiceover quoting convention.
    const voiceover = await screen.findByText(
      /voiceover: "it was a normal tuesday\."/i,
    )
    expect(voiceover.closest('[contenteditable]')).not.toBeNull()

    // Storyboard step gates on parsed scenes and renders the scene card.
    await user.click(screen.getByRole('button', { name: /^next$/i }))
    expect(await screen.findByText(/int\. office - day/i)).toBeInTheDocument()
    expect(screen.queryByText(/no scenes parsed/i)).not.toBeInTheDocument()
  })
})
