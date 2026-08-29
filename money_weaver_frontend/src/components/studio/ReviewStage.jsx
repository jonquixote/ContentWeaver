import { useState } from 'react'
import { useAuthStore } from '@/store/authStore'
import ApiService from '@/services/api'
import VideoProgressTracker from '@/components/VideoProgressTracker'
import { parseScriptText } from '@/lib/scriptParser'
import { toast } from 'sonner'

export default function ReviewStage({ state, projectId, onDone }) {
  const [taskId, setTaskId] = useState(null)
  const [busy, setBusy] = useState(false)
  const r = state.render
  const { scenes } = parseScriptText(state.script.scriptText || '')

  const create = async () => {
    const user = useAuthStore.getState().user
    if (!user?.id || projectId == null) {
      toast.error('Not ready — draft project missing')
      return
    }
    setBusy(true)
    try {
      const opts = {
        voice_type: r.voiceType,
        voice_id: r.voiceId,
        voice_override: r.voiceModelOverride || undefined,
        duration: Number(state.premise.durationSec),
        orientation: r.orientation,
        width: Number(r.width),
        height: Number(r.height),
      }
      const resp =
        r.workflowType === 'generative'
          ? await ApiService.generateGenerativeVideo(projectId, state.script.scriptText, {
              voice_id: r.voiceId,
              model: r.textModelOverride || undefined,
            })
          : await ApiService.generateAssemblerVideo(projectId, state.script.scriptText, opts)
      setTaskId(resp.task_id)
    } catch (e) {
      toast.error(e?.message || 'Failed to start video creation')
      setBusy(false)
    }
  }

  if (taskId) {
    return (
      <VideoProgressTracker
        taskId={taskId}
        onClose={() => {
          setTaskId(null)
          onDone?.()
        }}
      />
    )
  }

  return (
    <div className="space-y-4">
      <div
        className="rounded-md p-4 border"
        style={{ borderColor: 'var(--studio-border)', background: 'var(--studio-card)' }}
      >
        <h3 className="text-sm font-medium mb-2" style={{ color: 'var(--studio-text)' }}>
          {state.script.title || 'Untitled'}
        </h3>
        <p className="text-sm" style={{ color: 'var(--studio-muted)' }}>
          {state.premise.text}
        </p>
        {state.script.description && (
          <p className="text-sm mt-1" style={{ color: 'var(--studio-muted)' }}>
            {state.script.description}
          </p>
        )}
      </div>
      <div
        className="rounded-md p-4 border"
        style={{ borderColor: 'var(--studio-border)', background: 'var(--studio-card)' }}
      >
        <div className="grid grid-cols-2 gap-2 text-sm" style={{ color: 'var(--studio-text)' }}>
          <span>Scenes: {scenes.length}</span>
          <span>Workflow: {r.workflowType}</span>
          <span>Preset: {r.presetId ?? 'none'}</span>
          <span>
            Voice: {r.voiceType}
            {r.voiceId ? ` + clone #${r.voiceId}` : ''}
            {r.voiceModelOverride ? ' (API voice)' : ''}
          </span>
          <span>
            Resolution: {r.width}x{r.height}
          </span>
          <span>Language: {r.language}</span>
        </div>
      </div>
      <p className="text-xs" style={{ color: 'var(--studio-muted)' }}>
        Estimated processing time: {r.workflowType === 'generative' ? '5-15 min' : '2-5 min'}
      </p>
      <button
        type="button"
        disabled={busy}
        onClick={create}
        className="px-5 py-2 rounded-md text-sm font-semibold"
        style={{ background: 'var(--studio-accent)', color: '#06262b' }}
      >
        {busy ? 'Creating…' : 'Create video'}
      </button>
    </div>
  )
}