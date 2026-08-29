import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import StageTabs from '@/components/studio/StageTabs'
import PremiseStage from '@/components/studio/PremiseStage'
import ScriptStage from '@/components/studio/ScriptStage'
import StoryboardStage from '@/components/studio/StoryboardStage'
import RenderStage from '@/components/studio/RenderStage'
import ReviewStage from '@/components/studio/ReviewStage'
import useStudioSync from '@/hooks/useStudioSync'
import { validateStage } from '@/lib/studioState'

export default function Studio() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const { state, patch, ready, saveStatus, projectId: syncProjectId } = useStudioSync(projectId, (id) =>
    navigate(`/studio/${id}`, { replace: true }))
  const [stage, setStage] = useState(1)
  const [furthest, setFurthest] = useState(1)

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
        const v = validateStage(state, s)
        if (!v.ok) return // silently refuse; stage components surface errors
      }
    }
    setStage(n)
    setFurthest(Math.max(furthest, n))
    patch({ stage: n })
  }

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
      <main className="flex-1 overflow-y-auto p-6 max-w-3xl mx-auto w-full">
        {stage === 1 && <PremiseStage state={state} patch={patch} />}
        {stage === 2 && <ScriptStage state={state} patch={patch} />}
        {stage === 3 && <StoryboardStage state={state} patch={patch} />}
        {stage === 4 && <RenderStage state={state} patch={patch} />}
        {stage === 5 && (
          <ReviewStage state={state} projectId={syncProjectId} onDone={() => navigate('/dashboard')} />
        )}
      </main>
    </div>
  )
}