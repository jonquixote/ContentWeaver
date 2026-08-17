import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'

export function useProjects(options = {}) {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => api.getProjects(),
    ...options,
  })
}
