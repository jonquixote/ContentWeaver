import { renderHook, waitFor } from '@testing-library/react'
import { test, expect } from 'vitest'
import { makeQueryClient, makeWrapper } from '@/test/helpers'
import { useModels, useDefaultModel } from '../useModels'

test('fetches available models', async () => {
  const qc = makeQueryClient()
  const { result } = renderHook(() => useModels(), { wrapper: makeWrapper(qc) })
  await waitFor(() => expect(result.current.data).toHaveLength(1))
  expect(result.current.data[0]).toEqual({ id: 'gpt-4', name: 'GPT-4' })
})

test('fetches the default model', async () => {
  const qc = makeQueryClient()
  const { result } = renderHook(() => useDefaultModel(), { wrapper: makeWrapper(qc) })
  await waitFor(() => expect(result.current.data).toEqual({ id: 'gpt-4', name: 'GPT-4' }))
})