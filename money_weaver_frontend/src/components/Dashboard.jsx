import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Settings, LogOut, Eye, Play, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import api from '@/services/api'
import { useAuthStore } from '@/store/authStore'

const STATUS_COLORS = {
  draft: 'var(--studio-muted)',
  processing: 'var(--studio-accent)',
  completed: '#34d399',
  failed: '#f87171',
}

export default function Dashboard({ onCreateVideo }) {
  const navigate = useNavigate()
  const [projects, setProjects] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .getProjects()
      .then((list) => {
        if (!cancelled) setProjects(list ?? [])
      })
      .catch(() => {
        if (!cancelled) setProjects([])
        toast.error('Failed to load projects')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleLogout = async () => {
    try {
      await api.logout()
    } finally {
      useAuthStore.getState().logout()
      navigate('/login')
    }
  }

  const handleDelete = async (p) => {
    if (!window.confirm(`Delete "${p.title}"? This cannot be undone.`)) return
    try {
      await api.deleteProject(p.id)
      setProjects((prev) => prev.filter((x) => x.id !== p.id))
    } catch {
      toast.error('Failed to delete project')
    }
  }

  const newProject = onCreateVideo || (() => navigate('/studio'))

  return (
    <div className="min-h-screen studio-root flex flex-col">
      <header
        className="flex items-center justify-between px-6 h-14 border-b"
        style={{ borderColor: 'var(--studio-border)' }}
      >
        <span className="text-sm font-bold tracking-widest" style={{ color: 'var(--studio-text)' }}>
          CONTENT<span style={{ color: 'var(--studio-muted)' }}>WEAVER</span>{' '}
          <span style={{ color: 'var(--studio-accent)' }}>STUDIO</span>
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => navigate('/settings')}
            className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border"
            style={{ color: 'var(--studio-muted)', borderColor: 'var(--studio-border)' }}
          >
            <Settings className="h-3.5 w-3.5" />
            Settings
          </button>
          <button
            type="button"
            onClick={handleLogout}
            className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border"
            style={{ color: 'var(--studio-muted)', borderColor: 'var(--studio-border)' }}
          >
            <LogOut className="h-3.5 w-3.5" />
            Logout
          </button>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto max-w-4xl mx-auto w-full p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--studio-text)' }}>
            Projects
          </h2>
          <button
            type="button"
            onClick={newProject}
            aria-label="new project"
            className="inline-flex items-center gap-1.5 text-sm px-4 py-2 rounded-md font-semibold"
            style={{ background: 'var(--studio-accent)', color: '#06262b' }}
          >
            <Plus className="h-4 w-4" />
            New project
          </button>
        </div>

        {projects === null ? (
          <p className="text-sm" style={{ color: 'var(--studio-muted)' }}>
            Loading…
          </p>
        ) : projects.length === 0 ? (
          <div
            className="rounded-md p-8 text-center border"
            style={{ borderColor: 'var(--studio-border)', background: 'var(--studio-card)' }}
          >
            <p style={{ color: 'var(--studio-muted)' }}>
              No projects yet. Create your first video project.
            </p>
          </div>
        ) : (
          <div className="grid gap-3">
            {projects.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between rounded-md p-4 border"
                style={{ borderColor: 'var(--studio-border)', background: 'var(--studio-card)' }}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-medium truncate" style={{ color: 'var(--studio-text)' }}>
                      {p.title || 'Untitled'}
                    </h3>
                    <span
                      className="text-[10px] uppercase px-1.5 py-0.5 rounded"
                      style={{ color: STATUS_COLORS[p.status] || 'var(--studio-muted)', border: `1px solid ${STATUS_COLORS[p.status] || 'var(--studio-border)'}` }}
                    >
                      {p.status}
                    </span>
                  </div>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--studio-muted)' }}>
                    {p.workflow_type}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {p.status === 'draft' && (
                    <button
                      type="button"
                      onClick={() => navigate(`/studio/${p.id}`)}
                      aria-label="resume"
                      className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-md font-medium"
                      style={{ background: 'var(--studio-accent)', color: '#06262b' }}
                    >
                      <Play className="h-3.5 w-3.5" />
                      Resume
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => navigate(`/projects/${p.id}`)}
                    aria-label="open"
                    className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-md border"
                    style={{ color: 'var(--studio-text)', borderColor: 'var(--studio-border)' }}
                  >
                    <Eye className="h-3.5 w-3.5" />
                    Open
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(p)}
                    aria-label={`delete ${p.title}`}
                    className="text-xs px-2 py-1.5 rounded-md"
                    style={{ color: 'var(--studio-muted)' }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}