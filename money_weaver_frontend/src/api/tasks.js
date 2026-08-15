import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'

export function useTasks(options = {}) {
  return useQuery({
    queryKey: ['tasks'],
    queryFn: () => api.getTasks(),
    ...options,
  })
}