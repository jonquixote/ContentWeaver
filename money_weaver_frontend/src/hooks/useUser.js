import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'

export function useMe(options = {}) {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => api.getMe(),
    ...options,
  })
}