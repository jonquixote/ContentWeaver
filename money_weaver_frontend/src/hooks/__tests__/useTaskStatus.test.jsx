import { renderHook, act } from '@testing-library/react'
import { test, expect, vi, beforeEach, afterEach } from 'vitest'
import api from '@/services/api'
import { useTaskStatus } from '../useTaskStatus'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

test('polls task status and stops on a terminal state', async () => {
  const spy = vi.spyOn(api, 'getTaskStatus')
  spy.mockResolvedValueOnce({ status: 'running', progress: 50 })
    .mockResolvedValue({ status: 'completed', progress: 100 })

  const { result } = renderHook(() => useTaskStatus(7, true, 1000))

  await act(async () => { await Promise.resolve() })
  expect(spy).toHaveBeenCalledWith(7)
  expect(result.current.status).toEqual({ status: 'running', progress: 50 })

  await act(async () => { vi.advanceTimersByTime(1000) })
  await act(async () => { await Promise.resolve() })
  expect(result.current.status).toEqual({ status: 'completed', progress: 100 })
})

test('surfaces an error when the poll fails', async () => {
  const spy = vi.spyOn(api, 'getTaskStatus')
  spy.mockRejectedValue(new Error('boom'))

  const { result } = renderHook(() => useTaskStatus(7, true, 1000))

  await act(async () => { await Promise.resolve() })
  expect(result.current.error).toBeDefined()
  expect(result.current.status).toBeNull()
})