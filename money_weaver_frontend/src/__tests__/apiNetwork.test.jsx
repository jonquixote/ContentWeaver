import { describe, it, expect, vi, afterEach } from 'vitest'
import ApiService from '@/services/api'

describe('ApiService network handling', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('surfaces an actionable message when the server is unreachable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new TypeError('Failed to fetch')),
    )
    await expect(ApiService.request('/auth/login')).rejects.toThrow(
      /Cannot reach the server/,
    )
  })

  it('rethrows HTTP errors unchanged (non-network)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({}),
        headers: new Headers(),
      }),
    )
    // 401 triggers setToken(null) + redirect; avoid crashing the test env.
    await expect(ApiService.request('/auth/login')).rejects.toThrow()
  })
})
