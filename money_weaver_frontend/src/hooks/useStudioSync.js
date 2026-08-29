import { useCallback, useEffect, useRef, useState } from 'react'
import ApiService from '@/services/api'
import { defaultStudioState, SCHEMA_VERSION } from '@/lib/studioState'

const lsKey = (id) => `studio-draft-${id}`

const deepMerge = (base, patch) => {
  const out = { ...base }
  for (const [k, v] of Object.entries(patch || {})) {
    out[k] =
      v && typeof v === 'object' && !Array.isArray(v)
        ? deepMerge(base?.[k] ?? {}, v)
        : v
  }
  return out
}

export default function useStudioSync(projectId, onCreated = () => {}) {
  const [state, setState] = useState(defaultStudioState())
  const [ready, setReady] = useState(false)
  const [saveStatus, setSaveStatus] = useState('idle')
  const idRef = useRef(projectId ?? null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        if (projectId == null) {
          const p = await ApiService.createStudioProject()
          idRef.current = p.id
          onCreated(p.id)
        } else {
          idRef.current = projectId
          let serverState = null
          try {
            serverState = (await ApiService.getStudioState(projectId))?.studio_state ?? null
          } catch {
            serverState = null
          }
          if (serverState) {
            setState({ ...defaultStudioState(), ...serverState })
          } else {
            const raw = localStorage.getItem(lsKey(projectId))
            if (raw) setState({ ...defaultStudioState(), ...JSON.parse(raw) })
          }
        }
      } finally {
        if (!cancelled) setReady(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [projectId]) // eslint-disable-line react-hooks/exhaustive-deps

  const flush = useCallback(async (next) => {
    if (idRef.current == null) return
    setSaveStatus('saving')
    try {
      await ApiService.saveStudioState(idRef.current, {
        ...next,
        savedAt: undefined,
        updatedAt: new Date().toISOString(),
      })
      localStorage.removeItem(lsKey(idRef.current))
      setSaveStatus('saved')
    } catch {
      setSaveStatus('idle') // stays in localStorage; resilient
    }
  }, [])

  const patch = useCallback(
    (partial) => {
      setState((prev) => {
        const next = {
          ...deepMerge(prev, partial),
          updatedAt: new Date().toISOString(),
        }
        next.schemaVersion = SCHEMA_VERSION
        if (idRef.current != null) {
          localStorage.setItem(lsKey(idRef.current), JSON.stringify(next))
        }
        if (partial.stage) flush(next) // stage transitions sync to server
        return next
      })
    },
    [flush],
  )

  return { state, patch, ready, saveStatus, projectId: idRef.current }
}