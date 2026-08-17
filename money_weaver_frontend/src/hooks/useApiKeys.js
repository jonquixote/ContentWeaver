import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'

export function useApiKeys(userId, options = {}) {
  return useQuery({
    queryKey: ['api-keys', userId],
    queryFn: () => api.getApiKeys(userId),
    enabled: Boolean(userId),
    ...options,
  })
}

export function useAddApiKey(userId) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.addApiKey({ ...data, user_id: userId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['api-keys', userId] }),
  })
}

export function useDeleteApiKey(userId) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ apiKeyId }) => api.deleteApiKey(apiKeyId, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['api-keys', userId] }),
  })
}

export function useTestApiKey() {
  return useMutation({
    mutationFn: ({ provider, key }) => api.testApiKey(provider, key),
  })
}