import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ReviewStage from '@/components/studio/ReviewStage'
import ApiService from '@/services/api'
import { useAuthStore } from '@/store/authStore'

vi.mock('@/components/VideoProgressTracker', () => ({
  default: ({ taskId }) => <div data-testid="tracker">tracker-{taskId}</div>,
}))

const BASE = {
  premise: { text: 'cats code', durationSec: 60, nicheId: 'technology', sequenceProjectId: null },
  script: {
    title: 'Cats',
    description: 'desc',
    scriptHtml: '<p>x</p>',
    scriptText: '**Scene 1: A (0s-5s)**\nfoo\nVoiceover: "v"',
    characters: [],
  },
  storyboard: { overrides: {} },
  render: {
    presetId: 2,
    voiceType: 'female',
    voiceId: null,
    voiceModelOverride: null,
    textModelOverride: null,
    workflowType: 'assembler',
    orientation: 'portrait',
    width: '1080',
    height: '1920',
    language: 'en',
  },
}

beforeEach(() => {
  useAuthStore.setState({ user: { id: 1, email: 'test@test.com' }, token: 't' })
})

describe('ReviewStage', () => {
  it('create enqueues assembler on existing project id and starts tracker', async () => {
    const enq = vi.spyOn(ApiService, 'generateAssemblerVideo').mockResolvedValue({ task_id: 't-1' })
    render(<ReviewStage state={BASE} projectId={9} />)
    fireEvent.click(screen.getByRole('button', { name: /create video/i }))
    await screen.findByTestId('tracker')
    expect(enq).toHaveBeenCalledTimes(1)
    expect(enq.mock.calls[0][0]).toBe(9)
    expect(enq.mock.calls[0][1]).toBe(BASE.script.scriptText)
    expect(screen.getByTestId('tracker').textContent).toBe('tracker-t-1')
  })

  it('generative workflow enqueues generative and passes model', async () => {
    const gen = vi.spyOn(ApiService, 'generateGenerativeVideo').mockResolvedValue({ task_id: 't-2' })
    const state = {
      ...BASE,
      render: { ...BASE.render, workflowType: 'generative', textModelOverride: 'wan-x' },
    }
    render(<ReviewStage state={state} projectId={9} />)
    fireEvent.click(screen.getByRole('button', { name: /create video/i }))
    await screen.findByTestId('tracker')
    expect(gen.mock.calls[0][0]).toBe(9)
    expect(gen.mock.calls[0][2]).toEqual({ voice_id: null, model: 'wan-x' })
  })

  it('summarizes premise, scenes and resolution', () => {
    render(<ReviewStage state={BASE} projectId={9} />)
    expect(screen.getByText('Cats')).toBeInTheDocument()
    expect(screen.getByText('cats code')).toBeInTheDocument()
    expect(screen.getByText(/1080x1920/)).toBeInTheDocument()
  })
})