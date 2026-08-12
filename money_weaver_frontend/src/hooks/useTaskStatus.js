import { useState, useEffect, useCallback, useRef } from 'react'
import api from '@/services/api'

const TERMINAL = new Set(['completed', 'failed'])

export function useTaskStatus(taskId, enabled = false, intervalMs = 3000) {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const doneRef = useRef(false)
  const timerRef = useRef(null)

  const poll = useCallback(async () => {
    if (!taskId || !enabled || doneRef.current) return
    try {
      const res = await api.getTaskStatus(taskId)
      setStatus(res)
      setError(null)
      if (TERMINAL.has(res.status)) {
        doneRef.current = true
        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
      }
    } catch (err) {
      setError(err)
    }
  }, [taskId, enabled])

  useEffect(() => {
    if (!taskId || !enabled) return
    doneRef.current = false
    poll()
    const timer = setInterval(poll, intervalMs)
    timerRef.current = timer
    return () => {
      clearInterval(timer)
      timerRef.current = null
      doneRef.current = true
    }
  }, [taskId, enabled, intervalMs, poll])

  return { status, setStatus, error, refetch: poll }
}
