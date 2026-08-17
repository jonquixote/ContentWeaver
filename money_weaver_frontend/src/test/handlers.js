import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '@/services/api'

const base = API_BASE_URL

export const handlers = [
  http.get(`${base}/projects`, () => HttpResponse.json([{ id: 1, name: 'Project Alpha' }])),
  http.get(`${base}/tasks`, () => HttpResponse.json([{ id: 1, title: 'Task One', project_id: 1 }])),
  http.get(`${base}/presets`, () => HttpResponse.json([{ id: 1, name: 'Preset A' }])),
  http.get(`${base}/voices`, () => HttpResponse.json([{ id: 1, name: 'Voice A' }])),
  http.get(`${base}/users/me`, () => HttpResponse.json({ id: 1, email: 'test@test.com' })),
  http.get(`${base}/models`, () => HttpResponse.json([{ id: 'gpt-4', name: 'GPT-4' }])),
  http.get(`${base}/models/default`, () => HttpResponse.json({ id: 'gpt-4', name: 'GPT-4' })),
  http.get(`${base}/api-keys/user/:userId`, () => HttpResponse.json([{ id: 1, provider: 'openai' }])),
  http.post(`${base}/api-keys`, () => HttpResponse.json({ id: 2, provider: 'openai' }, { status: 201 })),
  http.delete(`${base}/api-keys/:apiKeyId`, () => HttpResponse.json({ ok: true })),
  http.post(`${base}/api-keys/test`, () => HttpResponse.json({ ok: true, valid: true })),
  http.get(`${base}/tasks/:taskId/status`, () => HttpResponse.json({ task_id: 1, status: 'completed', progress: 100 })),
]