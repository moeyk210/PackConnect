import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './messagingApi'
import { useRealtimeConnected, useRealtimeEvent } from './realtime'

export function useRequests(refreshKey) {
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const alive = useRef(false)
  const connected = useRealtimeConnected()
  const refresh = useCallback(async () => {
    try {
      const data = await api('/api/requests')
      if (alive.current) {
        setRequests(data.requests)
        setError('')
      }
    } catch (err) {
      if (alive.current) setError(err.message)
    } finally {
      if (alive.current) setLoading(false)
    }
  }, [])
  useEffect(() => {
    alive.current = true
    // Loads on mount, navigation and every (re)connect; polls only while the
    // socket is down. Request changes are pushed while connected.
    const initial = setTimeout(refresh, 0)
    const timer = connected ? null : setInterval(refresh, 8000)
    return () => {
      alive.current = false
      clearInterval(timer)
      clearTimeout(initial)
    }
  }, [refresh, refreshKey, connected])
  useRealtimeEvent('request', () => refresh())
  return { requests, loading, error, refresh }
}
