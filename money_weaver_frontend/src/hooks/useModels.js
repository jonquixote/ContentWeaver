import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'

export function useModels(options = {}) {
  return useQuery({
    queryKey: ['models'],
    queryFn: () => api.getAvailableModels(),
    ...options,
  })
}

export function useDefaultModel(options = {}) {
  return useQuery({
    queryKey: ['models', 'default'],
    queryFn: () => api.getDefaultModel(),
    ...options,
  })
}