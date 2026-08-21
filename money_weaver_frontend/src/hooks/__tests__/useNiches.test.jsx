import { test, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { API_BASE_URL } from '@/services/api'
import { makeQueryClient, makeWrapper } from '@/test/helpers'
import { useNiches } from '../useNiches'

test('fetches niches', async () => {
  const qc = makeQueryClient()
  const { result } = renderHook(() => useNiches(), { wrapper: makeWrapper(qc) })
  await waitFor(() => expect(result.current.data).toEqual(['personal_finance', 'fitness']))
  expect(result.current.isLoading).toBe(false)
})

test('surfaces an error when the request fails', async () => {
  server.use(
    http.get(`${API_BASE_URL}/niches`, () => HttpResponse.json({ error: 'boom' }, { status: 500 })),
  )
  const qc = makeQueryClient()
  const { result } = renderHook(() => useNiches(), { wrapper: makeWrapper(qc) })
  await waitFor(() => expect(result.current.isError).toBe(true))
  expect(result.current.error.message).toBe('boom')
})
