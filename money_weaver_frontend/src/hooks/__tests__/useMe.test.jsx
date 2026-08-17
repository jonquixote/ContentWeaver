import { renderHook, waitFor } from '@testing-library/react'
import { test, expect } from 'vitest'
import { makeQueryClient, makeWrapper } from '@/test/helpers'
import { useMe } from '../useUser'

test('fetches the current user', async () => {
  const qc = makeQueryClient()
  const { result } = renderHook(() => useMe(), { wrapper: makeWrapper(qc) })
  await waitFor(() => expect(result.current.data).toEqual({ id: 1, email: 'test@test.com' }))
})