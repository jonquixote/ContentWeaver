import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '@/services/api'

const base = API_BASE_URL

export const handlers = [
  http.get(`${base}/projects`, () => HttpResponse.json([{ id: 1, name: 'Project Alpha' }])),
  http.get(`${base}/tasks`, () => HttpResponse.json([{ id: 1, title: 'Task One', project_id: 1 }])),
  http.get(`${base}/presets`, () => HttpResponse.json([{ id: 1, name: 'Preset A' }])),
  http.get(`${base}/voices`, () => HttpResponse.json([{ id: 1, name: 'Voice A' }])),
  http.get(`${base}/users/me`, () => HttpResponse.json({ id: 1, email: 'test@test.com' })),
  http.get(`${base}/models`, () =>
    HttpResponse.json({
      models: [
        { id: 'poolside/laguna-s-2.1:free', label: 'Laguna S 2.1', provider: 'openrouter', kind: 'text', free: true },
        {
          id: 'nvidia/nemotron-3.5-lightning:free',
          label: 'Nemotron Lightning',
          provider: 'openrouter',
          kind: 'text',
          free: true,
        },
        // display_name instead of label exercises the normalize bridge.
        { id: 'fal-ai/wan-t2v', display_name: 'Wan 2.2 T2V (fal)', provider: 'fal', kind: 'video', free: false },
      ],
    }),
  ),
  http.get(`${base}/models/default`, () => HttpResponse.json({ id: 'gpt-4', name: 'GPT-4' })),
  http.get(`${base}/api-keys/user/:userId`, () => HttpResponse.json([{ id: 1, provider: 'openai' }])),
  http.post(`${base}/api-keys`, () => HttpResponse.json({ id: 2, provider: 'openai' }, { status: 201 })),
  http.delete(`${base}/api-keys/:apiKeyId`, () => HttpResponse.json({ ok: true })),
  http.post(`${base}/api-keys/test`, () => HttpResponse.json({ ok: true, valid: true })),
  http.get(`${base}/tasks/:taskId/status`, () => HttpResponse.json({ task_id: 1, status: 'completed', progress: 100 })),
  http.get(`${base}/tasks/:taskId`, () => HttpResponse.json({ id: 77, status: 'completed', progress: 100 })),
  http.post(`${base}/generate/surprise`, () => HttpResponse.json({ task_id: 77 }, { status: 202 })),
  http.post(`${base}/enhance-prompt`, () =>
    HttpResponse.json({ enhanced: 'An enhanced prompt with vivid detail' })),
  http.get(`${base}/settings/models`, () => HttpResponse.json({ defaults: {}, fallbacks: [] })),
  http.get(`${base}/model-assignments`, () => HttpResponse.json({ assignments: {} })),
  http.put(`${base}/model-assignments`, () => HttpResponse.json({ ok: true })),
  http.get(`${base}/youtube/auth-url`, () => HttpResponse.json({ url: 'https://accounts.google.com/o/oauth2/auth?client_id=test' })),
  http.get(`${base}/niches`, () => HttpResponse.json({ niches: ['personal_finance', 'fitness'] })),
  http.get(`${base}/topics`, () => HttpResponse.json({
    topics: [
      { title: 'How to budget on a low income', source: 'reddit', url: 'https://example.com/t/1' },
      { title: 'Emergency fund basics', source: 'youtube', url: 'https://example.com/t/2' },
    ],
  })),
]