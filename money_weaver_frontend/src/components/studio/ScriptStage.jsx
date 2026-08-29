import { useState } from 'react'
import { X } from 'lucide-react'
import ScriptEditor from '@/components/ScriptEditor'
import AIGenButton from '@/components/studio/AIGenButton'
import ApiService from '@/services/api'
import { parseScreenplay, extractCharacters } from '@/lib/screenplayBlocks'
import { scriptTextToHtml } from '@/lib/studioUtils'

const inputCls = 'w-full rounded-md p-2.5 text-sm border'
const inputStyle = {
  background: 'var(--studio-surface)',
  borderColor: 'var(--studio-border)',
  color: 'var(--studio-text)',
}

export default function ScriptStage({ state, patch }) {
  const s = state.script
  const [charName, setCharName] = useState('')
  const setScript = (updates) => patch({ script: { ...s, ...updates } })

  const hasScript = Boolean((s.scriptText || '').trim())
  const autoChars = extractCharacters(s.scriptText ? parseScreenplay(s.scriptText) : [])
  const manual = (s.characters || []).map((c) => c.name.toUpperCase())
  const merged = [...new Set([...autoChars, ...manual])].sort()

  const handleDraft = async () => {
    if (hasScript && !window.confirm('Replace the current script with a generated draft?')) return
    const r = await ApiService.draftScript({
      topic: state.premise.text,
      duration: state.premise.durationSec,
      niche_id: state.premise.nicheId || undefined,
    })
    const text = r?.script ?? ''
    setScript({ scriptHtml: scriptTextToHtml(text), scriptText: text })
  }

  const handleEnhance = async () => {
    const r = await ApiService.enhancePrompt(s.scriptText)
    const text = (r.enhanced || '').trim()
    if (!text) return
    if (!window.confirm('Replace script with the enhanced version?')) return
    setScript({ scriptHtml: scriptTextToHtml(text), scriptText: text })
  }

  const addChar = () => {
    const name = charName.trim().toUpperCase()
    if (!name) return
    setScript({ characters: [...(s.characters || []), { name, traits: [] }] })
    setCharName('')
  }
  const removeChar = (name) =>
    setScript({ characters: (s.characters || []).filter((c) => c.name.toUpperCase() !== name) })

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-1">
          <label htmlFor="script-title" className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>
            Title
          </label>
          <AIGenButton
            label="title"
            disabled={!state.premise.text.trim()}
            onGenerate={async () => {
              const r = await ApiService.enhancePrompt(
                `${state.premise.text} — write a punchy video title (6-10 words, title case)`,
              )
              setScript({ title: (r.enhanced || '').trim() })
            }}
          />
        </div>
        <input
          id="script-title"
          value={s.title}
          onChange={(e) => setScript({ title: e.target.value })}
          className={inputCls}
          style={inputStyle}
          placeholder="Video title"
        />
      </div>

      <div>
        <div className="flex items-center justify-between mb-1">
          <label htmlFor="script-desc" className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>
            Description
          </label>
          <AIGenButton
            label="description"
            disabled={!state.premise.text.trim()}
            onGenerate={async () => {
              const r = await ApiService.generateDescription(state.premise.text, s.scriptText)
              setScript({ description: (r.description || '').trim() })
            }}
          />
        </div>
        <textarea
          id="script-desc"
          rows={2}
          value={s.description}
          onChange={(e) => setScript({ description: e.target.value })}
          className={inputCls}
          style={inputStyle}
          placeholder="Shown on the video platform / project card"
        />
      </div>

      <div className="flex items-center gap-3">
        <span className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>
          Script
        </span>
        <AIGenButton label="draft" disabled={!state.premise.text.trim()} onGenerate={handleDraft} />
        <AIGenButton label="enhance" disabled={!hasScript} onGenerate={handleEnhance} />
      </div>

      <ScriptEditor
        value={s.scriptHtml}
        onChange={(html, text) => setScript({ scriptHtml: html, scriptText: text })}
      />

      <div>
        <span className="text-xs font-semibold tracking-widest uppercase" style={{ color: 'var(--studio-muted)' }}>
          Characters
        </span>
        <div className="flex flex-wrap gap-2 mt-2">
          {merged.map((name) => (
            <span
              key={name}
              className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded"
              style={{
                background: 'var(--studio-surface)',
                border: '1px solid var(--studio-border)',
                color: 'var(--studio-text)',
              }}
            >
              {name}
              {manual.includes(name) && (
                <button
                  type="button"
                  aria-label={`remove ${name}`}
                  onClick={() => removeChar(name)}
                  className="text-slate-500 hover:text-red-400"
                >
                  <X size={12} />
                </button>
              )}
            </span>
          ))}
        </div>
        <div className="flex gap-2 mt-2">
          <input
            value={charName}
            onChange={(e) => setCharName(e.target.value)}
            placeholder="Character name"
            className={inputCls + ' flex-1'}
            style={inputStyle}
          />
          <button
            type="button"
            onClick={addChar}
            aria-label="add character"
            className="px-3 py-1.5 text-xs rounded-md"
            style={{
              background: 'var(--studio-surface)',
              border: '1px solid var(--studio-border)',
              color: 'var(--studio-text)',
            }}
          >
            Add
          </button>
        </div>
      </div>
    </div>
  )
}