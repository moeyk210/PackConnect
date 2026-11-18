import { act } from '@testing-library/react'
import { RealtimeContext } from '../realtime'

// A stand-in for createConnection(): tests fire server events and toggle
// connectivity without a socket.
export function fakeRealtime({ connected = true } = {}) {
  const handlers = new Map()
  const listeners = new Set()
  const sent = []
  let isConnected = connected
  const connection = {
    socket: {
      on(event, fn) {
        handlers.set(event, [...(handlers.get(event) || []), fn])
      },
      off(event, fn) {
        handlers.set(
          event,
          (handlers.get(event) || []).filter((h) => h !== fn),
        )
      },
      emit(...args) {
        sent.push(args)
      },
    },
    isConnected: () => isConnected,
    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
  }
  return {
    sent,
    wrapper: ({ children }) => (
      <RealtimeContext.Provider value={connection}>
        {children}
      </RealtimeContext.Provider>
    ),
    fire(event, data) {
      act(() => (handlers.get(event) || []).forEach((h) => h(data)))
    },
    setConnected(value) {
      act(() => {
        isConnected = value
        listeners.forEach((listener) => listener())
      })
    },
    subscribers: (event) => (handlers.get(event) || []).length,
  }
}
