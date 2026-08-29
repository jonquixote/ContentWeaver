import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Key, ListChecks, Plus, Trash2, CheckCircle2, XCircle } from 'lucide-react'
import api from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import { useModels } from '@/hooks/useModels'
import ModelPicker from '@/components/ModelPicker'

const PROVIDERS = ['openrouter', 'nvidia', 'fal']

const ASSIGNMENT_ROWS = [
  { task: 'idea', label: 'Idea Generation', kinds: ['text'] },
  { task: 'script', label: 'Script Writing', kinds: ['text'] },
  { task: 'enhance', label: 'Prompt Enhance', kinds: ['text'] },
  { task: 'voice_tts', label: 'Voice TTS', kinds: ['voice'] },
  { task: 'video_gen', label: 'Video Generation', kinds: ['video'] },
]

const inputStyle = {
  background: 'var(--studio-surface)',
  borderColor: 'var(--studio-border)',
  color: 'var(--studio-text)',
}
const sectionTitle = 'text-xs font-semibold tracking-widest uppercase'

export default function SettingsPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)

  const [apiKeys, setApiKeys] = useState([])
  const [newKey, setNewKey] = useState({ name: '', provider: 'openrouter', key: '' })
  const [testResult, setTestResult] = useState(null)
  const [assignments, setAssignments] = useState({})
  const models = useModels().data?.models ?? []

  useEffect(() => {
    let cancelled = false
    api.getApiKeys(user?.id).then((d) => {
      if (!cancelled) setApiKeys(d?.api_keys ?? [])
    })
    api.getModelAssignments().then((d) => {
      if (!cancelled) setAssignments(d?.assignments ?? {})
    })
    return () => {
      cancelled = true
    }
  }, [user?.id])

  const handleAddKey = async () => {
    if (!newKey.name || !newKey.key) {
      toast.error('Please provide a name and key')
      return
    }
    try {
      await api.addApiKey({ name: newKey.name, provider: newKey.provider, key: newKey.key })
      setNewKey({ name: '', provider: 'openrouter', key: '' })
      const d = await api.getApiKeys(user?.id)
      setApiKeys(d?.api_keys ?? [])
      toast.success('API key added')
    } catch (e) {
      toast.error(e?.message || 'Failed to add API key')
    }
  }

  const handleDeleteKey = async (id) => {
    if (!window.confirm('Delete this API key?')) return
    try {
      await api.deleteApiKey(id, user?.id)
      setApiKeys((prev) => prev.filter((k) => k.id !== id))
    } catch (e) {
      toast.error(e?.message || 'Failed to delete API key')
    }
  }

  const handleTestKey = async () => {
    if (!newKey.provider || !newKey.key) {
      toast.error('Select a provider and enter a key')
      return
    }
    try {
      const r = await api.testApiKey(newKey.provider, newKey.key)
      setTestResult({ ok: true, data: r })
    } catch (e) {
      setTestResult({ ok: false, error: e?.message })
    }
  }

  const handleAssignmentChange = async (task, modelId) => {
    const next = { ...assignments, [task]: modelId }
    setAssignments(next)
    try {
      await api.updateModelAssignments({ assignments: { [task]: modelId } })
    } catch (e) {
      toast.error(e?.message || 'Failed to save assignment')
    }
  }

  return (
    <div className="min-h-screen studio-root flex flex-col">
      <header
        className="flex items-center justify-between px-6 h-14 border-b"
        style={{ borderColor: 'var(--studio-border)' }}
      >
        <span className="text-sm font-bold tracking-widest" style={{ color: 'var(--studio-text)' }}>
          CONTENT<span style={{ color: 'var(--studio-muted)' }}>WEAVER</span>{' '}
          <span style={{ color: 'var(--studio-accent)' }}>SETTINGS</span>
        </span>
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="text-xs px-3 py-1.5 rounded-md border"
          style={{ color: 'var(--studio-muted)', borderColor: 'var(--studio-border)' }}
        >
          Back
        </button>
      </header>

      <main className="flex-1 overflow-y-auto max-w-3xl mx-auto w-full p-6 space-y-6">
        {/* Card 1: API Keys */}
        <div
          className="rounded-md p-5 border"
          style={{ borderColor: 'var(--studio-border)', background: 'var(--studio-card)' }}
        >
          <div className="flex items-center gap-2 mb-1">
            <Key className="h-4 w-4" style={{ color: 'var(--studio-accent)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--studio-text)' }}>
              API Keys
            </h2>
          </div>
          <p className="text-xs mb-4" style={{ color: 'var(--studio-muted)' }}>
            Manage provider keys used for LLM generation.
          </p>

          <div className="grid grid-cols-2 gap-3 mb-3">
            <input
              value={newKey.name}
              onChange={(e) => setNewKey((p) => ({ ...p, name: e.target.value }))}
              placeholder="Name"
              aria-label="key name"
              className="rounded-md p-2.5 text-sm border"
              style={inputStyle}
            />
            <select
              value={newKey.provider}
              onChange={(e) => setNewKey((p) => ({ ...p, provider: e.target.value }))}
              className="rounded-md p-2.5 text-sm border"
              style={inputStyle}
            >
              {PROVIDERS.map((pr) => (
                <option key={pr} value={pr}>
                  {pr}
                </option>
              ))}
            </select>
          </div>
          <input
            type="password"
            value={newKey.key}
            onChange={(e) => setNewKey((p) => ({ ...p, key: e.target.value }))}
            placeholder="API key"
            aria-label="key value"
            className="w-full rounded-md p-2.5 text-sm border mb-3"
            style={inputStyle}
          />
          <div className="flex items-center gap-2 mb-3">
            <button
              type="button"
              onClick={handleAddKey}
              className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-md font-medium"
              style={{ background: 'var(--studio-accent)', color: '#06262b' }}
            >
              <Plus className="h-3.5 w-3.5" />
              Add key
            </button>
            <button
              type="button"
              onClick={handleTestKey}
              className="text-xs px-3 py-1.5 rounded-md border"
              style={{ color: 'var(--studio-text)', borderColor: 'var(--studio-border)' }}
            >
              Test
            </button>
            {testResult && (
              <span
                className="inline-flex items-center gap-1 text-xs"
                style={{ color: testResult.ok ? '#34d399' : '#f87171' }}
              >
                {testResult.ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                {testResult.ok ? 'valid' : 'invalid'}
              </span>
            )}
          </div>

          {apiKeys.length === 0 ? (
            <p className="text-xs" style={{ color: 'var(--studio-muted)' }}>
              No API keys saved yet.
            </p>
          ) : (
            <div className="space-y-2">
              {apiKeys.map((k) => (
                <div
                  key={k.id}
                  className="flex items-center justify-between p-2.5 rounded-md border"
                  style={{ borderColor: 'var(--studio-border)', background: 'var(--studio-surface)' }}
                >
                  <div>
                    <span className="text-sm" style={{ color: 'var(--studio-text)' }}>
                      {k.name}
                    </span>
                    <span className="text-xs ml-2" style={{ color: 'var(--studio-muted)' }}>
                      {k.provider}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDeleteKey(k.id)}
                    aria-label={`delete ${k.name}`}
                    style={{ color: 'var(--studio-muted)' }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Card 2: Model Assignments */}
        <div
          className="rounded-md p-5 border"
          style={{ borderColor: 'var(--studio-border)', background: 'var(--studio-card)' }}
        >
          <div className="flex items-center gap-2 mb-1">
            <ListChecks className="h-4 w-4" style={{ color: 'var(--studio-accent)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--studio-text)' }}>
              Model Assignments
            </h2>
          </div>
          <p className="text-xs mb-4" style={{ color: 'var(--studio-muted)' }}>
            Choose which model each generative task uses.
          </p>

          <div className="space-y-3">
            {ASSIGNMENT_ROWS.map((row) => (
              <div key={row.task} className="flex items-center justify-between gap-4">
                <span className={sectionTitle} style={{ color: 'var(--studio-muted)' }}>
                  {row.label}
                </span>
                <div className="w-64">
                  <ModelPicker
                    models={models}
                    value={assignments[row.task] || null}
                    onChange={(modelId) => handleAssignmentChange(row.task, modelId)}
                    kinds={row.kinds}
                    compact
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}