import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'

export function useTopics(niche, limit = 20, options = {}) {
  return useQuery({
    queryKey: ['topics', niche, limit],
    queryFn: async () => {
      const res = await api.fetchTopics(niche, limit)
      return res?.topics ?? []
    },
    enabled: Boolean(niche),
    ...options,
  })
}
