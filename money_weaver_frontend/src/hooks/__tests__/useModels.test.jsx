import { renderHook, waitFor } from '@testing-library/react'
import { test, expect } from 'vitest'
import { makeQueryClient, makeWrapper } from '@/test/helpers'
import { useModels, useDefaultModel } from '../useModels'

test('fetches available models', async () => {
  const qc = makeQueryClient()
  const { result } = renderHook(() => useModels(), { wrapper: makeWrapper(qc) })
  await waitFor(() => expect(result.current.data?.models).toHaveLength(3))
  expect(result.current.data.models[0]).toEqual({
    id: 'poolside/laguna-s-2.1:free',
    label: 'Laguna S 2.1',
    provider: 'openrouter',
    kind: 'text',
    free: true,
  })
})

test('fetches the default model', async () => {
  const qc = makeQueryClient()
  const { result } = renderHook(() => useDefaultModel(), { wrapper: makeWrapper(qc) })
  await waitFor(() => expect(result.current.data).toEqual({ id: 'gpt-4', name: 'GPT-4' }))
})