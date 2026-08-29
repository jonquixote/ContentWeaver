import { useState } from 'react'
import AIGenButton from '@/components/studio/AIGenButton'
import ApiService from '@/services/api'
import { DURATIONS } from '@/lib/studioState'

const fmt = (s) => (s % 60 === 0 ? `${s / 60} minute${s > 60 ? 's' : ''}` : `${s} seconds`)

export default function PremiseStage({ state, patch }) {
  const [topics, setTopics] = useState([])
  const p = state.premise
  const setPremise = (updates) => patch({ premise: { ...p, ...updates } })

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-1">
          <label
            htmlFor="premise"
            className="text-xs font-semibold tracking-widest uppercase"
            style={{ color: 'var(--studio-muted)' }}
          >
            Premise
          </label>
          <AIGenButton
            label="suggest"
            onGenerate={async () => {
              const r = await ApiService.randomIdea({})
              setPremise({ text: r.topic || r.title || '' })
            }}
          />
        </div>
        <textarea
          id="premise"
          rows={3}
          value={p.text}
          onChange={(e) => setPremise({ text: e.target.value })}
          placeholder="What's the video about?"
          className="w-full rounded-md p-3 text-sm border outline-none focus:ring-1"
          style={{
            background: 'var(--studio-surface)',
            borderColor: 'var(--studio-border)',
            color: 'var(--studio-text)',
          }}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label
            htmlFor="duration"
            className="block text-xs font-semibold tracking-widest uppercase mb-1"
            style={{ color: 'var(--studio-muted)' }}
          >
            Duration
          </label>
          <select
            id="duration"
            value={p.durationSec}
            onChange={(e) => setPremise({ durationSec: Number(e.target.value) })}
            className="w-full rounded-md p-2.5 text-sm border"
            style={{
              background: 'var(--studio-surface)',
              borderColor: 'var(--studio-border)',
              color: 'var(--studio-text)',
            }}
          >
            {DURATIONS.map((d) => (
              <option key={d} value={d}>
                {fmt(d)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <div className="flex items-center justify-between mb-1">
            <label
              htmlFor="niche"
              className="text-xs font-semibold tracking-widest uppercase"
              style={{ color: 'var(--studio-muted)' }}
            >
              Niche
            </label>
            <AIGenButton
              label="discover"
              disabled={!p.nicheId}
              onGenerate={async () => {
                const r = await ApiService.fetchTopics(p.nicheId, 20)
                setTopics(r?.topics ?? [])
              }}
            />
          </div>
          <input
            id="niche"
            value={p.nicheId}
            placeholder="e.g. technology"
            onChange={(e) => setPremise({ nicheId: e.target.value })}
            className="w-full rounded-md p-2.5 text-sm border"
            style={{
              background: 'var(--studio-surface)',
              borderColor: 'var(--studio-border)',
              color: 'var(--studio-text)',
            }}
          />
        </div>
      </div>

      {topics.length > 0 && (
        <div className="space-y-1" role="list">
          {topics.map((t) => (
            <button
              key={t.title}
              type="button"
              onClick={() => setPremise({ text: t.title })}
              className="block w-full text-left text-sm rounded-md px-3 py-2 border hover:border-[var(--studio-accent)] transition-colors"
              style={{
                background: 'var(--studio-surface)',
                borderColor: 'var(--studio-border)',
                color: 'var(--studio-text)',
              }}
            >
              {t.title}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}