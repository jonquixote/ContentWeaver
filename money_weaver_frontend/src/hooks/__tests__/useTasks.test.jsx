import { renderHook, waitFor } from '@testing-library/react'
import { test, expect } from 'vitest'
import { makeQueryClient, makeWrapper } from '@/test/helpers'
import { useTasks } from '../useTasks'

test('fetches tasks', async () => {
  const qc = makeQueryClient()
  const { result } = renderHook(() => useTasks(), { wrapper: makeWrapper(qc) })
  await waitFor(() => expect(result.current.data).toHaveLength(1))
  expect(result.current.data[0]).toEqual({ id: 1, title: 'Task One', project_id: 1 })
})