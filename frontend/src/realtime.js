import {
  createContext,
  useContext,
  useEffect,
  useEffectEvent,
  useSyncExternalStore,
} from 'react'
import { io } from 'socket.io-client'

// Retries for the cases socket.io-client does not retry by itself: the server
// refused the connection or disconnected this socket (e.g. password reset).
// Transport drops are retried by the client's own backoff.
export const RETRY_DELAYS_MS = [2000, 5000, 15000, 30000]

export const RealtimeContext = createContext(null)

export function createConnection() {
  // Same origin; the session cookie authenticates the socket.
  const socket = io({ autoConnect: false })
  const listeners = new Set()
  let connected = false
  const setConnected = (value) => {
    if (value === connected) return
    connected = value
    listeners.forEach((listener) => listener())
  }
  return {
    socket,
    isConnected: () => connected,
    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    start() {
      let retry
      let attempt = 0
      const up = () => {
        attempt = 0
        setConnected(true)
      }
      const down = () => {
        setConnected(false)
        if (socket.active) return
        clearTimeout(retry)
        const delay =
          RETRY_DELAYS_MS[Math.min(attempt, RETRY_DELAYS_MS.length - 1)]
        attempt += 1
        retry = setTimeout(() => socket.connect(), delay)
      }
      socket.on('connect', up)
      socket.on('disconnect', down)
      socket.on('connect_error', down)
      socket.connect()
      return () => {
        clearTimeout(retry)
        socket.off('connect', up)
        socket.off('disconnect', down)
        socket.off('connect_error', down)
        socket.disconnect()
        setConnected(false)
      }
    },
  }
}

const offline = () => false
const noSubscription = () => () => {}

// True while the socket is connected. Components poll as a fallback when false.
export function useRealtimeConnected() {
  const connection = useContext(RealtimeContext)
  return useSyncExternalStore(
    connection ? connection.subscribe : noSubscription,
    connection ? connection.isConnected : offline,
  )
}

// Calls handler for each server event; the latest handler is always used.
export function useRealtimeEvent(event, handler) {
  const connection = useContext(RealtimeContext)
  const onEvent = useEffectEvent((...args) => handler(...args))
  useEffect(() => {
    if (!connection) return undefined
    const listener = (...args) => onEvent(...args)
    connection.socket.on(event, listener)
    return () => connection.socket.off(event, listener)
  }, [connection, event])
}
