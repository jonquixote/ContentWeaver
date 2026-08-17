import { renderHook, waitFor } from '@testing-library/react'
import { test, expect } from 'vitest'
import { makeQueryClient, makeWrapper } from '@/test/helpers'
import { usePresets } from '../usePresets'

test('fetches presets', async () => {
  const qc = makeQueryClient()
  const { result } = renderHook(() => usePresets(), { wrapper: makeWrapper(qc) })
  await waitFor(() => expect(result.current.data).toHaveLength(1))
  expect(result.current.data[0]).toEqual({ id: 1, name: 'Preset A' })
})