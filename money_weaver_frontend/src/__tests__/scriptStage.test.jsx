import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ScriptStage from '@/components/studio/ScriptStage'
import ApiService from '@/services/api'

vi.mock('@/components/ScriptEditor', () => ({
  default: () => <div data-testid="script-editor" />,
}))

const BASE = {
  premise: { text: 'A cat learns to code', durationSec: 60, nicheId: 'technology', sequenceProjectId: null },
  script: { title: '', description: '', scriptHtml: '', scriptText: '', characters: [] },
}

describe('ScriptStage', () => {
  it('title ✦ sets title from premise via enhance-prompt', async () => {
    vi.spyOn(ApiService, 'enhancePrompt').mockResolvedValue({ enhanced: 'Cat Codes!' })
    const patch = vi.fn()
    render(<ScriptStage state={BASE} patch={patch} />)
    fireEvent.click(screen.getByRole('button', { name: /AI title/i }))
    await waitFor(() => expect(patch).toHaveBeenCalled())
    expect(patch.mock.calls.at(-1)[0].script.title).toBe('Cat Codes!')
  })

  it('description ✦ calls /generate/description with premise+script', async () => {
    const spy = vi.spyOn(ApiService, 'generateDescription').mockResolvedValue({ description: 'A cat joins a team.' })
    const patch = vi.fn()
    render(<ScriptStage state={{ ...BASE, script: { ...BASE.script, scriptText: 'SCENE…' } }} patch={patch} />)
    fireEvent.click(screen.getByRole('button', { name: /AI description/i }))
    await waitFor(() => expect(spy).toHaveBeenCalledWith('A cat learns to code', 'SCENE…'))
    expect(patch.mock.calls.at(-1)[0].script.description).toContain('cat joins')
  })

  it('draft fills editor with canonical screenplay (storyboard-safe)', async () => {
    const draftText = '**Scene 1: Opening (0s-5s)**\ncat at desk\nVoiceover: "The cat codes."\n'
    vi.spyOn(ApiService, 'draftScript').mockResolvedValue({ script: draftText })
    const patch = vi.fn()
    render(<ScriptStage state={BASE} patch={patch} />)
    fireEvent.click(screen.getByRole('button', { name: /AI draft/i }))
    await waitFor(() => expect(patch).toHaveBeenCalled())
    const upd = patch.mock.calls.at(-1)[0].script
    expect(upd.scriptText).toContain('Voiceover:')
    expect(upd.scriptHtml).toContain('<strong>Scene 1: Opening (0s-5s)</strong>')
  })

  it('enhance is disabled with empty script (improve-only)', () => {
    render(<ScriptStage state={BASE} patch={() => {}} />)
    expect(screen.getByRole('button', { name: /AI enhance/i })).toBeDisabled()
  })

  it('draft asks before overwriting existing script', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    vi.spyOn(ApiService, 'draftScript').mockResolvedValue({ script: 'x' })
    const patch = vi.fn()
    render(
      <ScriptStage
        state={{ ...BASE, script: { ...BASE.script, scriptText: 'existing', scriptHtml: '<p>x</p>' } }}
        patch={patch}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /AI draft/i }))
    await waitFor(() => expect(confirmSpy).toHaveBeenCalled())
    expect(patch).not.toHaveBeenCalled()
    confirmSpy.mockRestore()
  })

  it('auto-extracts dialogue characters from script text', () => {
    const scriptText = '**Scene 1: A (0s-5s)**\nJANE:\n[DIALOGUE: Hi]\nVoiceover: "x"'
    render(<ScriptStage state={{ ...BASE, script: { ...BASE.script, scriptText } }} patch={() => {}} />)
    expect(screen.getByText('JANE')).toBeInTheDocument()
  })

  it('adds manual character to state', () => {
    const patch = vi.fn()
    render(<ScriptStage state={BASE} patch={patch} />)
    fireEvent.change(screen.getByPlaceholderText(/character name/i), { target: { value: 'MILO' } })
    fireEvent.click(screen.getByRole('button', { name: /add character/i }))
    expect(patch.mock.calls.at(-1)[0].script.characters).toEqual([{ name: 'MILO', traits: [] }])
  })
})