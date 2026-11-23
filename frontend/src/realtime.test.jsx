import { StrictMode } from 'react'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import RealtimeProvider from './RealtimeProvider'
import {
  RETRY_DELAYS_MS,
  useRealtimeConnected,
  useRealtimeEvent,
} from './realtime'
import { response, student } from './test/fixtures'

// Mirrors the socket.io-client semantics the hook relies on: `active` stays
// true while the client retries by itself, and is false after the server
// refused or ended the connection.
const sockets = vi.hoisted(() => [])
vi.mock('socket.io-client', () => ({
  io: vi.fn((options) => {
    const handlers = new Map()
    const socket = {
      options,
      active: false,
      connects: 0,
      disconnects: 0,
      on(event, fn) {
        handlers.set(event, [...(handlers.get(event) || []), fn])
      },
      off(event, fn) {
        handlers.set(
          event,
          (handlers.get(event) || []).filter((h) => h !== fn),
        )
      },
      listeners: (event) => handlers.get(event) || [],
      connect() {
        this.active = true
        this.connects += 1
      },
      disconnect() {
        this.active = false
        this.disconnects += 1
      },
      fire(event, ...args) {
        act(() => (handlers.get(event) || []).forEach((h) => h(...args)))
      },
    }
    sockets.push(socket)
    return socket
  }),
}))
vi.mock('./App', () => ({
  default: ({ onLogout }) => <button onClick={onLogout}>Sign out</button>,
}))

function Probe({ onEvent }) {
  const connected = useRealtimeConnected()
  useRealtimeEvent('chat_message', onEvent)
  return <p>{connected ? 'live' : 'offline'}</p>
}

beforeEach(() => {
  sockets.length = 0
})
afterEach(() => vi.useRealTimers())

describe('RealtimeProvider', () => {
  it('opens one same-origin socket and reports connection state', () => {
    render(
      <RealtimeProvider>
        <Probe onEvent={() => {}} />
      </RealtimeProvider>,
    )
    const started = sockets.filter((s) => s.connects)
    expect(started).toHaveLength(1)
    expect(started[0].options).toEqual({ autoConnect: false })
    expect(screen.getByText('offline')).toBeInTheDocument()
    started[0].fire('connect')
    expect(screen.getByText('live')).toBeInTheDocument()
    started[0].active = true // transport drop: the client retries by itself
    started[0].fire('disconnect', 'transport close')
    expect(screen.getByText('offline')).toBeInTheDocument()
  })

  it('delivers events to the latest handler and unsubscribes on unmount', () => {
    const first = vi.fn()
    const second = vi.fn()
    const view = render(
      <RealtimeProvider>
        <Probe onEvent={first} />
      </RealtimeProvider>,
    )
    const socket = sockets.find((s) => s.connects)
    view.rerender(
      <RealtimeProvider>
        <Probe onEvent={second} />
      </RealtimeProvider>,
    )
    socket.fire('chat_message', { request_id: 7 })
    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledWith({ request_id: 7 })
    view.unmount()
    expect(socket.listeners('chat_message')).toHaveLength(0)
    expect(socket.disconnects).toBeGreaterThan(0)
  })

  it('retries with backoff only when the client will not retry itself', () => {
    vi.useFakeTimers()
    render(
      <RealtimeProvider>
        <Probe onEvent={() => {}} />
      </RealtimeProvider>,
    )
    const socket = sockets.find((s) => s.connects)
    socket.active = true
    socket.fire('connect_error', new Error('transport'))
    act(() => vi.advanceTimersByTime(RETRY_DELAYS_MS.at(-1)))
    expect(socket.connects).toBe(1)
    socket.active = false // refused by the server
    socket.fire('connect_error', new Error('unauthorized'))
    act(() => vi.advanceTimersByTime(RETRY_DELAYS_MS[0] - 1))
    expect(socket.connects).toBe(1)
    act(() => vi.advanceTimersByTime(1))
    expect(socket.connects).toBe(2)
    socket.active = false
    socket.fire('disconnect', 'io server disconnect')
    act(() => vi.advanceTimersByTime(RETRY_DELAYS_MS[1]))
    expect(socket.connects).toBe(3)
    socket.fire('connect')
    expect(screen.getByText('live')).toBeInTheDocument()
    // A successful connection resets the backoff to the shortest delay.
    socket.active = false
    socket.fire('connect_error', new Error('unavailable'))
    act(() => vi.advanceTimersByTime(RETRY_DELAYS_MS[0]))
    expect(socket.connects).toBe(4)
  })

  it('stops a pending retry when unmounted', () => {
    vi.useFakeTimers()
    const view = render(
      <RealtimeProvider>
        <Probe onEvent={() => {}} />
      </RealtimeProvider>,
    )
    const socket = sockets.find((s) => s.connects)
    socket.active = false
    socket.fire('connect_error', new Error('unavailable'))
    view.unmount()
    act(() => vi.advanceTimersByTime(RETRY_DELAYS_MS.at(-1)))
    expect(socket.connects).toBe(1)
  })

  it('keeps exactly one live socket under StrictMode', () => {
    render(
      <StrictMode>
        <RealtimeProvider>
          <Probe onEvent={() => {}} />
        </RealtimeProvider>
      </StrictMode>,
    )
    const started = sockets.filter((s) => s.connects)
    expect(started).toHaveLength(1) // a discarded initializer never connects
    expect(started[0].active).toBe(true)
    started[0].fire('connect')
    expect(screen.getByText('live')).toBeInTheDocument()
  })

  it('is inert outside a provider so components fall back to polling', () => {
    const onEvent = vi.fn()
    render(<Probe onEvent={onEvent} />)
    expect(screen.getByText('offline')).toBeInTheDocument()
    expect(sockets).toHaveLength(0)
  })
})

describe('AuthShell socket lifetime', () => {
  it('connects after sign-in and disconnects on sign-out', async () => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {}) // not in jsdom
    window.location.hash = '#/app'
    fetch.mockImplementation(async (url) =>
      url === '/api/auth/me'
        ? response({ student })
        : response({ status: 'ok' }),
    )
    const { default: AuthShell } = await import('./AuthShell')
    render(<AuthShell />)
    const signOut = await screen.findByRole('button', { name: 'Sign out' })
    // The socket connects just after the signed-in page appears, so wait for it
    // rather than checking straight away (slower machines can lag behind).
    await waitFor(() => expect(sockets.find((s) => s.connects)).toBeDefined())
    const socket = sockets.find((s) => s.connects)
    act(() => {
      window.location.hash = '#/app/requests' // navigation keeps the socket
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
    expect(sockets.filter((s) => s.connects)).toEqual([socket])
    expect(socket.disconnects).toBe(0)
    await userEvent.click(signOut)
    expect(fetch).toHaveBeenCalledWith('/api/auth/logout', { method: 'POST' })
    expect(socket.disconnects).toBe(1)
  })
})
