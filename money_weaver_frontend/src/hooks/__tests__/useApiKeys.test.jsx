import { renderHook, waitFor, act } from '@testing-library/react'
import { test, expect, vi } from 'vitest'
import { makeQueryClient, makeWrapper } from '@/test/helpers'
import { useApiKeys, useAddApiKey, useDeleteApiKey, useTestApiKey } from '../useApiKeys'

const USER_ID = 42

test('fetches api keys for a user', async () => {
  const qc = makeQueryClient()
  const { result } = renderHook(() => useApiKeys(USER_ID), { wrapper: makeWrapper(qc) })
  await waitFor(() => expect(result.current.data).toEqual([{ id: 1, provider: 'openai' }]))
})

test('does not fetch when no userId is provided', async () => {
  const qc = makeQueryClient()
  const { result } = renderHook(() => useApiKeys(), { wrapper: makeWrapper(qc) })
  expect(result.current.fetchStatus).toBe('idle')
  expect(result.current.data).toBeUndefined()
})

test('useAddApiKey posts and invalidates the api-keys query', async () => {
  const qc = makeQueryClient()
  const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
  const { result } = renderHook(() => useAddApiKey(USER_ID), { wrapper: makeWrapper(qc) })
  await act(async () => {
    result.current.mutate({ provider: 'openai', key: 'sk-test' })
  })
  await waitFor(() => expect(result.current.isSuccess).toBe(true))
  expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['api-keys', USER_ID] })
})

test('useDeleteApiKey deletes and invalidates the api-keys query', async () => {
  const qc = makeQueryClient()
  const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
  const { result } = renderHook(() => useDeleteApiKey(USER_ID), { wrapper: makeWrapper(qc) })
  await act(async () => {
    result.current.mutate({ apiKeyId: 5 })
  })
  await waitFor(() => expect(result.current.isSuccess).toBe(true))
  expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['api-keys', USER_ID] })
})

test('useTestApiKey posts to the test endpoint', async () => {
  const qc = makeQueryClient()
  const { result } = renderHook(() => useTestApiKey(), { wrapper: makeWrapper(qc) })
  await act(async () => {
    result.current.mutate({ provider: 'openai', key: 'sk-test' })
  })
  await waitFor(() => expect(result.current.isSuccess).toBe(true))
  expect(result.current.data).toEqual({ ok: true, valid: true })
})