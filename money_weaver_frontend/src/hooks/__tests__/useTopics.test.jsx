import { test, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { makeQueryClient, makeWrapper } from '@/test/helpers'
import { useTopics } from '../useTopics'

test('fetches topics for a niche', async () => {
  const qc = makeQueryClient()
  const { result } = renderHook(() => useTopics('personal_finance'), { wrapper: makeWrapper(qc) })
  await waitFor(() => expect(result.current.data).toHaveLength(2))
  expect(result.current.data[0]).toEqual({
    title: 'How to budget on a low income',
    source: 'reddit',
    url: 'https://example.com/t/1',
  })
})

test('stays idle without a niche', async () => {
  const qc = makeQueryClient()
  const { result } = renderHook(() => useTopics(null), { wrapper: makeWrapper(qc) })
  expect(result.current.fetchStatus).toBe('idle')
  expect(result.current.data).toBeUndefined()
})
