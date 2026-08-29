import AIGenButton from '@/components/studio/AIGenButton'
import { parseScriptText } from '@/lib/scriptParser'
import ApiService from '@/services/api'

const inputStyle = {
  background: 'var(--studio-surface)',
  borderColor: 'var(--studio-border)',
  color: 'var(--studio-text)',
}

export default function StoryboardStage({ state, patch }) {
  const { scenes } = parseScriptText(state.script?.scriptText || '')
  const overrides = state.storyboard?.overrides || {}

  const setOverride = (sceneNumber, updates) =>
    patch({
      storyboard: {
        overrides: { ...overrides, [sceneNumber]: { ...overrides[sceneNumber], ...updates } },
      },
    })

  const total = scenes.reduce(
    (sum, s) => sum + (overrides[s.scene_number]?.durationSec ?? s.duration),
    0,
  )

  const handleImage = (sceneNumber, file) => {
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => setOverride(sceneNumber, { imageKey: reader.result })
    reader.readAsDataURL(file)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>
          Storyboard
        </span>
        <span
          className="text-xs px-2 py-1 rounded"
          style={{
            background: 'var(--studio-surface)',
            border: '1px solid var(--studio-border)',
            color: 'var(--studio-text)',
          }}
          data-testid="total-duration"
        >
          {scenes.length} scene{scenes.length === 1 ? '' : 's'} · {total}s
        </span>
      </div>

      {scenes.map((scene) => {
        const ov = overrides[scene.scene_number] || {}
        return (
          <div
            key={scene.scene_number}
            data-testid={`scene-card-${scene.scene_number}`}
            className="rounded-md p-4 border"
            style={{ borderColor: 'var(--studio-border)', background: 'var(--studio-card)' }}
          >
            <div className="flex items-center justify-between mb-2">
              <h5 className="text-sm font-medium" style={{ color: 'var(--studio-text)' }}>
                Scene {scene.scene_number}: {scene.description}
              </h5>
              <span className="text-xs" style={{ color: 'var(--studio-muted)' }}>
                {ov.durationSec ?? scene.duration}s
              </span>
            </div>

            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>
                Visual
              </label>
              <AIGenButton
                label="suggest"
                onGenerate={async () => {
                  const r = await ApiService.enhancePrompt(
                    `Scene ${scene.scene_number} (${scene.description}): vivid visual for stock/AI video. Script: ${state.script.scriptText}`,
                  )
                  setOverride(scene.scene_number, { visualText: (r.enhanced || '').trim() })
                }}
              />
            </div>
            <textarea
              rows={2}
              value={ov.visualText ?? scene.visual_description}
              placeholder="visual description"
              onChange={(e) => setOverride(scene.scene_number, { visualText: e.target.value })}
              className="w-full rounded-md p-2 text-sm border"
              style={{ ...inputStyle, borderColor: 'var(--studio-border)' }}
            />

            <div className="flex items-center gap-3 mt-2">
              <label className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>
                Duration
              </label>
              <input
                type="number"
                min={1}
                max={120}
                value={ov.durationSec ?? scene.duration}
                onChange={(e) => setOverride(scene.scene_number, { durationSec: Number(e.target.value) })}
                className="w-20 rounded-md p-1.5 text-sm border"
                style={{ ...inputStyle, borderColor: 'var(--studio-border)' }}
              />
              <label className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>
                Reference image
              </label>
              <input
                type="file"
                accept="image/*"
                className="text-xs"
                style={{ color: 'var(--studio-muted)' }}
                onChange={(e) => handleImage(scene.scene_number, e.target.files?.[0])}
              />
              {ov.imageKey && (
                <img
                  alt="reference"
                  className="h-10 w-10 rounded object-cover border"
                  style={{ borderColor: 'var(--studio-border)' }}
                  src={ov.imageKey}
                />
              )}
            </div>

            {scene.voiceover && (
              <p className="text-sm mt-2" style={{ color: 'var(--studio-muted)' }}>
                “{scene.voiceover}”
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}