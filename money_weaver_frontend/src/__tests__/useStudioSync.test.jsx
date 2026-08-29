import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import useStudioSync from '@/hooks/useStudioSync'
import ApiService from '@/services/api'

beforeEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('useStudioSync', () => {
  it('creates draft on first use when no projectId, then navigates', async () => {
    const onCreated = vi.fn()
    vi.spyOn(ApiService, 'createStudioProject').mockResolvedValue({ id: 42 })
    const { result } = renderHook(() => useStudioSync(undefined, onCreated))
    await waitFor(() => expect(result.current.ready).toBe(true))
    expect(onCreated).toHaveBeenCalledWith(42)
  })

  it('localStorage immediate, server sync on patch with stage change', async () => {
    vi.spyOn(ApiService, 'getStudioState').mockResolvedValue({ studio_state: null })
    const save = vi.spyOn(ApiService, 'saveStudioState').mockResolvedValue({ saved_at: 'x' })
    const { result } = renderHook(() => useStudioSync(7, () => {}))
    await waitFor(() => expect(result.current.ready).toBe(true))
    act(() => {
      result.current.patch({
        premise: { text: 'cats', durationSec: 60, nicheId: '', sequenceProjectId: null },
      })
    })
    expect(localStorage.getItem('studio-draft-7')).toContain('cats')
    await act(async () => {
      result.current.patch({ stage: 2 })
    })
    expect(save).toHaveBeenCalled()
    expect(localStorage.getItem('studio-draft-7')).toBeNull()
  })

  it('server state wins on load; localStorage used only when server empty', async () => {
    localStorage.setItem(
      'studio-draft-9',
      JSON.stringify({ premise: { text: 'local' } }),
    )
    vi.spyOn(ApiService, 'getStudioState').mockResolvedValue({
      studio_state: { premise: { text: 'server' } },
    })
    const { result } = renderHook(() => useStudioSync(9, () => {}))
    await waitFor(() => expect(result.current.ready).toBe(true))
    expect(result.current.state.premise.text).toBe('server')
  })

  it('404 getStudioState falls back to null (treated as empty)', async () => {
    vi.spyOn(ApiService, 'getStudioState').mockRejectedValue(new Error('HTTP error! status: 404'))
    const { result } = renderHook(() => useStudioSync(11, () => {}))
    await waitFor(() => expect(result.current.ready).toBe(true))
    expect(result.current.state.premise.text).toBe('')
  })
})