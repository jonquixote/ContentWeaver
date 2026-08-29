import { useState } from 'react'
import { Sparkles, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

export default function AIGenButton({ label, onGenerate, disabled }) {
  const [busy, setBusy] = useState(false)
  const handle = async () => {
    if (busy || disabled) return
    setBusy(true)
    try {
      await onGenerate()
    } catch (e) {
      toast.error(e?.message || `${label} failed`)
    } finally {
      setBusy(false)
    }
  }
  return (
    <button
      type="button"
      onClick={handle}
      disabled={disabled || busy}
      aria-label={`AI ${label}`}
      className="inline-flex items-center gap-1 text-xs text-[var(--studio-accent)] hover:opacity-80 disabled:opacity-40 transition-opacity"
    >
      {busy
        ? <Loader2 className="h-3.5 w-3.5 animate-spin" role="status" />
        : <Sparkles className="h-3.5 w-3.5" />}
      {label}
    </button>
  )
}