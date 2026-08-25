import { useMemo, useState } from 'react'
import { ChevronDown, X } from 'lucide-react'

function normalize(model) {
  const id = typeof model === 'string' ? model : model?.id
  if (!id) return null
  const label = typeof model === 'string' ? model : (model?.label || model?.display_name || model?.id)
  return {
    id,
    label,
    provider: typeof model === 'object' && model ? model?.provider ?? null : null,
    kind: typeof model === 'object' && model ? model?.kind ?? null : null,
    free: Boolean(typeof model === 'object' && model ? model?.free : false),
  }
}

export default function ModelPicker({ models = [], value, onChange, kinds = null, compact = false }) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [providerFilter, setProviderFilter] = useState('')

  const allOptions = useMemo(() => models.map(normalize).filter(Boolean), [models])
  const kindFiltered = useMemo(
    () => (kinds ? allOptions.filter((m) => m.kind != null && kinds.includes(m.kind)) : allOptions),
    [allOptions, kinds],
  )

  const providers = useMemo(() => [...new Set(kindFiltered.map((m) => m.provider).filter(Boolean))].sort(), [kindFiltered])

  const visibleOptions = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return kindFiltered
      .filter((m) => (providerFilter ? m.provider === providerFilter : true))
      .filter((m) => {
        if (!needle) return true
        return m.id.toLowerCase().includes(needle) || m.label.toLowerCase().includes(needle)
      })
      .sort(
        (a, b) =>
          Number(b.free) - Number(a.free) ||
          a.label.localeCompare(b.label) ||
          a.id.localeCompare(b.id),
      )
  }, [kindFiltered, providerFilter, q])

  const selected = allOptions.find((m) => m.id === value) ?? null

  const pick = (id) => {
    onChange(id)
    setOpen(false)
    setQ('')
    setProviderFilter('')
  }

  const chipBase = compact
    ? 'px-2 py-0.5 text-xs rounded-full border transition-colors'
    : 'px-3 py-1 text-sm rounded-full border transition-colors'

  return (
    <div className="relative w-full">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`flex w-full items-center justify-between gap-2 rounded-md bg-slate-700 text-white ${
          compact ? 'px-2 py-1 text-xs' : 'px-3 py-2 text-sm'
        }`}
      >
        <span className="truncate">{selected ? selected.label : 'Select a model...'}</span>
        {open ? (
          <X className={`${compact ? 'h-3 w-3' : 'h-4 w-4'} shrink-0 text-slate-400`} />
        ) : (
          <ChevronDown className={`${compact ? 'h-3 w-3' : 'h-4 w-4'} shrink-0 text-slate-400`} />
        )}
      </button>

      {open && (
        <div
          data-testid="model-picker-panel"
          className="absolute z-50 mt-1 w-full rounded-md border border-slate-600 bg-slate-800 p-2 shadow-lg"
        >
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search models..."
            className={`w-full rounded-md border border-slate-600 bg-slate-700 text-white placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500 ${
              compact ? 'px-2 py-1 text-xs' : 'px-3 py-2 text-sm'
            }`}
          />

          <div className="mt-2 flex flex-wrap gap-1">
            {[['', 'All'], ...providers.map((p) => [p, p])].map(([key, name]) => {
              const active = providerFilter === key
              return (
                <button
                  key={key || 'all'}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setProviderFilter(key)}
                  className={`${chipBase} ${
                    active
                      ? 'border-blue-500 bg-blue-600/30 text-white'
                      : 'border-slate-600 text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  {name}
                </button>
              )
            })}
          </div>

          <ul role="listbox" className="mt-2 max-h-64 overflow-y-auto">
            {visibleOptions.length === 0 && (
              <li className={`${compact ? 'px-2 py-1 text-xs' : 'px-3 py-2 text-sm'} text-slate-400`}>
                No matching models
              </li>
            )}
            {visibleOptions.map((m) => (
              <li key={m.id} role="option" aria-selected={m.id === value}>
                <button
                  type="button"
                  onClick={() => pick(m.id)}
                  className={`flex w-full items-center gap-2 rounded-md text-left hover:bg-slate-700 ${
                    m.id === value ? 'bg-slate-700' : ''
                  } ${compact ? 'px-2 py-1 text-xs' : 'px-3 py-2 text-sm'}`}
                >
                  <span className="truncate text-white">
                    {m.label}
                    {m.provider ? <span className="text-slate-400"> · {m.provider}</span> : null}
                  </span>
                  {m.free && (
                    <span
                      className={`shrink-0 rounded-full border border-emerald-600/40 bg-emerald-900/40 font-medium text-emerald-300 ${
                        compact ? 'ml-auto px-1.5 text-[10px]' : 'ml-auto px-2 text-xs'
                      }`}
                    >
                      Free
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
