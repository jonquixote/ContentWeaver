import ModelPicker from '@/components/ModelPicker'
import { useModels } from '@/hooks/useModels'
import { usePresets } from '@/hooks/usePresets'
import { useVoices } from '@/hooks/useVoices'

const inputStyle = {
  background: 'var(--studio-surface)',
  borderColor: 'var(--studio-border)',
  color: 'var(--studio-text)',
}
const sectionLabel = 'text-xs font-semibold tracking-widest uppercase'

export default function RenderStage({ state, patch }) {
  const r = state.render
  const setRender = (updates) => patch({ render: { ...r, ...updates } })
  const presets = usePresets().data ?? []
  const voices = useVoices().data ?? []
  const models = useModels().data?.models ?? []
  const apiVoices = models.filter((m) => m?.kind === 'voice')

  return (
    <div className="space-y-6">
      <div>
        <label className={sectionLabel} style={{ color: 'var(--studio-muted)' }}>
          Workflow
        </label>
        <div role="radiogroup" className="flex gap-4 mt-2">
          {['assembler', 'generative'].map((w) => (
            <label key={w} className="flex items-center gap-2 text-sm" style={{ color: 'var(--studio-text)' }}>
              <input
                type="radio"
                name="workflow"
                value={w}
                checked={r.workflowType === w}
                onChange={() => setRender({ workflowType: w })}
              />{' '}
              {w}
            </label>
          ))}
        </div>
      </div>

      <div>
        <label htmlFor="preset" className={sectionLabel} style={{ color: 'var(--studio-muted)' }}>
          Preset
        </label>
        <select
          id="preset"
          value={r.presetId ?? ''}
          onChange={(e) => {
            const preset = presets.find((p) => p.id === Number(e.target.value)) || null
            if (!preset) return setRender({ presetId: null })
            setRender({
              presetId: preset.id,
              width: String(preset.width),
              height: String(preset.height),
              orientation:
                preset.width > preset.height ? 'landscape' : preset.width < preset.height ? 'portrait' : 'square',
            })
          }}
          className="w-full mt-2 rounded-md p-2.5 text-sm border"
          style={{ ...inputStyle, borderColor: 'var(--studio-border)' }}
        >
          <option value="">Select a preset…</option>
          {presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} — {p.width}x{p.height}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="voiceType" className={sectionLabel} style={{ color: 'var(--studio-muted)' }}>
          Voice type
        </label>
        <select
          id="voiceType"
          value={r.voiceType}
          onChange={(e) => setRender({ voiceType: e.target.value })}
          className="w-full mt-2 rounded-md p-2.5 text-sm border"
          style={{ ...inputStyle, borderColor: 'var(--studio-border)' }}
        >
          {['female', 'male', 'neutral'].map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className={sectionLabel} style={{ color: 'var(--studio-muted)' }}>
          Cloned voice
        </label>
        <select
          value={r.voiceId ?? 'default'}
          onChange={(e) => setRender({ voiceId: e.target.value === 'default' ? null : Number(e.target.value) })}
          className="w-full mt-2 rounded-md p-2.5 text-sm border"
          style={{ ...inputStyle, borderColor: 'var(--studio-border)' }}
        >
          <option value="default">Default (chain)</option>
          {voices.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
        </select>
      </div>

      {apiVoices.length > 0 && (
        <div>
          <label className={sectionLabel} style={{ color: 'var(--studio-muted)' }}>
            API voices
          </label>
          <div className="grid gap-2 mt-2">
            {apiVoices.map((m) => (
              <button
                key={m.id}
                type="button"
                aria-pressed={r.voiceModelOverride === m.id}
                onClick={() => setRender({ voiceModelOverride: r.voiceModelOverride === m.id ? null : m.id })}
                className="text-left px-3 py-2 rounded-md border text-sm"
                style={{
                  borderColor: r.voiceModelOverride === m.id ? 'var(--studio-accent)' : 'var(--studio-border)',
                  color: 'var(--studio-text)',
                }}
              >
                {m.label || m.display_name || m.id}
                {m.provider && (
                  <span className="text-xs block" style={{ color: 'var(--studio-muted)' }}>
                    {m.provider}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={sectionLabel} style={{ color: 'var(--studio-muted)' }}>
            Text model override
          </label>
          <ModelPicker
            models={models}
            value={r.textModelOverride}
            onChange={(v) => setRender({ textModelOverride: v })}
            kinds={['text']}
            compact
          />
        </div>
        <div>
          <label className={sectionLabel} style={{ color: 'var(--studio-muted)' }}>
            Language
          </label>
          <select
            value={r.language}
            onChange={(e) => setRender({ language: e.target.value })}
            className="w-full mt-2 rounded-md p-2.5 text-sm border"
            style={{ ...inputStyle, borderColor: 'var(--studio-border)' }}
          >
            {['en', 'es', 'fr', 'de', 'zh'].map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  )
}