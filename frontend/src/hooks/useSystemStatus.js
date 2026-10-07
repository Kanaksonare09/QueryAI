import { useState, useEffect, useCallback } from 'react'
import { getSystemStatus } from '../api/client'

export function useSystemStatus(intervalMs = 30_000) {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const data = await getSystemStatus()
      setStatus(data)
    } catch {
      setStatus(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, intervalMs)
    return () => clearInterval(id)
  }, [refresh, intervalMs])

  return { status, loading, refresh }
}
