import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'

export function useNiches(options = {}) {
  return useQuery({
    queryKey: ['niches'],
    queryFn: async () => {
      const res = await api.getNiches()
      return res?.niches ?? []
    },
    ...options,
  })
}
