import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import StageTabs from '@/components/studio/StageTabs'
import PremiseStage from '@/components/studio/PremiseStage'
import ScriptStage from '@/components/studio/ScriptStage'
import StoryboardStage from '@/components/studio/StoryboardStage'
import RenderStage from '@/components/studio/RenderStage'
import ReviewStage from '@/components/studio/ReviewStage'
import useStudioSync from '@/hooks/useStudioSync'
import { usePresets } from '@/hooks/usePresets'
import { validateStage } from '@/lib/studioState'

export default function Studio() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const { state, patch, ready, saveStatus, projectId: syncProjectId } = useStudioSync(projectId, (id) =>
    navigate(`/studio/${id}`, { replace: true }))
  const [stage, setStage] = useState(1)
  const [furthest, setFurthest] = useState(1)
  const presets = usePresets().data ?? []

  useEffect(() => {
    if (ready) {
      setStage(state.stage || 1)
      setFurthest(state.stage || 1)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready])

  if (!ready) {
    return (
      <div
        className="min-h-screen studio-root flex items-center justify-center text-sm"
        style={{ color: 'var(--studio-muted)' }}
      >
        Loading…
      </div>
    )
  }

  const goTo = (n) => {
    if (n > stage) {
      for (let s = stage; s < n; s++) {
        const v = validateStage(state, s, { presets })
        if (!v.ok) return // silently refuse; stage components surface errors
      }
    }
    setStage(n)
    setFurthest(Math.max(furthest, n))
    patch({ stage: n })
  }

  const gateOk = validateStage(state, stage, { presets }).ok
  const next = () => stage < 5 && goTo(stage + 1)

  return (
    <div className="studio-root min-h-screen flex flex-col">
      <header
        className="flex items-center justify-between px-4 h-14 border-b"
        style={{ borderColor: 'var(--studio-border)' }}
      >
        <span className="text-sm font-bold tracking-widest" style={{ color: 'var(--studio-text)' }}>
          CONTENT<span style={{ color: 'var(--studio-muted)' }}>WEAVER</span>{' '}
          <span style={{ color: 'var(--studio-accent)' }}>STUDIO</span>
        </span>
        <span className="text-xs" style={{ color: 'var(--studio-muted)' }} role="status">
          {saveStatus === 'saving' ? 'Saving…' : saveStatus === 'saved' ? 'Saved' : ''}
        </span>
      </header>
      <StageTabs current={stage} furthest={furthest} onGo={goTo} />
      <main className="flex-1 flex overflow-y-auto p-6 max-w-3xl mx-auto w-full">
        <div className="m-auto w-full">
          {stage === 1 && <PremiseStage state={state} patch={patch} />}
          {stage === 2 && <ScriptStage state={state} patch={patch} />}
          {stage === 3 && <StoryboardStage state={state} patch={patch} />}
          {stage === 4 && <RenderStage state={state} patch={patch} />}
          {stage === 5 && (
            <ReviewStage state={state} projectId={syncProjectId} onDone={() => navigate('/dashboard')} />
          )}
        </div>
      </main>
      <footer
        className="flex items-center justify-between px-6 py-4 max-w-3xl mx-auto w-full"
        style={{ borderTop: '1px solid var(--studio-border)' }}
      >
        <button
          type="button"
          onClick={() => stage > 1 && goTo(stage - 1)}
          disabled={stage <= 1}
          className="text-sm px-4 py-2 rounded-md border disabled:opacity-40"
          style={{ color: 'var(--studio-muted)', borderColor: 'var(--studio-border)' }}
        >
          Back
        </button>
        {stage < 5 && (
          <button
            type="button"
            onClick={next}
            disabled={!gateOk}
            className="text-sm px-5 py-2 rounded-md font-semibold disabled:opacity-40"
            style={{ background: 'var(--studio-accent)', color: '#06262b' }}
          >
            Next
          </button>
        )}
      </footer>
    </div>
  )
}