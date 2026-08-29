import { STAGES } from '@/lib/studioState'

const HUES = { 1: '#22d3ee', 2: '#a78bfa', 3: '#fbbf24', 4: '#34d399', 5: '#f87171' }

export default function StageTabs({ current, furthest, onGo }) {
  return (
    <div
      className="flex items-center gap-1 px-4 py-2 border-b"
      style={{ borderColor: 'var(--studio-border)' }}
      role="tablist"
    >
      {STAGES.map((s) => {
        const enabled = s.id <= furthest
        const active = s.id === current
        return (
          <button
            key={s.id}
            role="tab"
            aria-selected={active}
            disabled={!enabled}
            onClick={() => enabled && onGo(s.id)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
              active
                ? 'text-white'
                : enabled
                  ? 'text-slate-400 hover:text-slate-200'
                  : 'text-slate-600'
            }`}
            style={active ? { background: 'var(--studio-surface)' } : undefined}
          >
            <span
              className="inline-block w-1.5 h-1.5 rounded-full mr-1.5 align-middle"
              style={{ background: HUES[s.id] }}
            />
            {s.id} {s.label}
          </button>
        )
      })}
    </div>
  )
}