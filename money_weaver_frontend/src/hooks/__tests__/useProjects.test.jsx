import { renderHook, waitFor } from '@testing-library/react'
import { test, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { API_BASE_URL } from '@/services/api'
import { makeQueryClient, makeWrapper } from '@/test/helpers'
import { useProjects } from '../useProjects'

test('fetches projects', async () => {
  const qc = makeQueryClient()
  const { result } = renderHook(() => useProjects(), { wrapper: makeWrapper(qc) })
  await waitFor(() => expect(result.current.data).toHaveLength(1))
  expect(result.current.data[0]).toEqual({ id: 1, name: 'Project Alpha' })
  expect(result.current.isLoading).toBe(false)
})

test('surfaces an error when the request fails', async () => {
  server.use(
    http.get(`${API_BASE_URL}/projects`, () => HttpResponse.json({ error: 'boom' }, { status: 500 })),
  )
  const qc = makeQueryClient()
  const { result } = renderHook(() => useProjects(), { wrapper: makeWrapper(qc) })
  await waitFor(() => expect(result.current.isError).toBe(true))
  expect(result.current.error.message).toBe('boom')
})