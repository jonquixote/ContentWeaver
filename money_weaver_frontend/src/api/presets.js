import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'

export function usePresets(options = {}) {
  return useQuery({
    queryKey: ['presets'],
    queryFn: () => api.getPresets(),
    ...options,
  })
}