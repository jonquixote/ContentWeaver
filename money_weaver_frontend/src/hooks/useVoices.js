import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'

export function useVoices(options = {}) {
  return useQuery({
    queryKey: ['voices'],
    queryFn: () => api.getVoices(),
    ...options,
  })
}
