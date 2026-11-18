import { act, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import NotificationBell from './NotificationBell'
import MeetingPanel from './MeetingPanel'
import { BlockedStudents, ConversationInbox } from './Community'
import { useRequests } from './useRequests'
import { deferred, response, student } from './test/fixtures'
import { fakeRealtime } from './test/realtime'

const calls = (path) =>
  fetch.mock.calls.filter(
    ([url, options]) => url === path && options?.method !== 'POST',
  ).length
const idle = (ms) => act(() => vi.advanceTimersByTimeAsync(ms))
const bell = (count) =>
  screen.findByRole('button', { name: `Notifications, ${count} unread` })

afterEach(() => vi.useRealTimers())

function RequestCount() {
  const { requests } = useRequests('app')
  return <p>{requests.length} requests</p>
}

describe('notification bell', () => {
  it('refreshes on pushes and never polls while connected', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fetch.mockResolvedValue(response({ notifications: [], unread_count: 0 }))
    const live = fakeRealtime()
    render(<NotificationBell route="app" />, { wrapper: live.wrapper })
    await bell(0)
    await idle(30000)
    expect(calls('/api/notifications')).toBe(1)
    fetch.mockResolvedValue(response({ notifications: [], unread_count: 3 }))
    live.fire('notifications', {})
    await bell(3)
    expect(calls('/api/notifications')).toBe(2)
  })

  it('polls every 5 s while disconnected and refreshes once on reconnect', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fetch.mockResolvedValue(response({ notifications: [], unread_count: 0 }))
    const live = fakeRealtime({ connected: false })
    render(<NotificationBell route="app" />, { wrapper: live.wrapper })
    await bell(0)
    await idle(5000)
    await waitFor(() => expect(calls('/api/notifications')).toBe(2))
    live.setConnected(true)
    await waitFor(() => expect(calls('/api/notifications')).toBe(3))
    await idle(30000)
    expect(calls('/api/notifications')).toBe(3)
  })

  it('never lets an older response overwrite a newer pushed refresh', async () => {
    const first = deferred()
    const second = deferred()
    fetch.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const live = fakeRealtime()
    render(<NotificationBell route="app" />, { wrapper: live.wrapper })
    live.fire('notifications', {})
    second.resolve(response({ notifications: [], unread_count: 2 }))
    await bell(2)
    first.resolve(response({ notifications: [], unread_count: 1 }))
    await act(async () => {})
    expect(
      screen.getByRole('button', { name: 'Notifications, 2 unread' }),
    ).toBeInTheDocument()
  })
})

describe('notification bell polling', () => {
  it('keeps a single poll when a push interrupts a fetch while disconnected', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const first = deferred()
    fetch
      .mockReturnValueOnce(first.promise)
      .mockResolvedValue(response({ notifications: [], unread_count: 0 }))
    const live = fakeRealtime({ connected: false })
    render(<NotificationBell route="app" />, { wrapper: live.wrapper })
    live.fire('notifications', {}) // supersedes the first fetch
    first.resolve(response({ notifications: [], unread_count: 0 }))
    await bell(0)
    expect(calls('/api/notifications')).toBe(2)
    await idle(5000)
    await waitFor(() => expect(calls('/api/notifications')).toBe(3))
    await idle(4000)
    expect(calls('/api/notifications')).toBe(3) // not two parallel chains
  })
})

describe('requests list', () => {
  it('refreshes on request pushes instead of the 8 s interval', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fetch.mockResolvedValue(response({ requests: [] }))
    const live = fakeRealtime()
    render(<RequestCount />, { wrapper: live.wrapper })
    await screen.findByText('0 requests')
    await idle(30000)
    expect(calls('/api/requests')).toBe(1)
    fetch.mockResolvedValue(response({ requests: [{ id: 7 }] }))
    live.fire('request', { request_id: 7 })
    expect(await screen.findByText('1 requests')).toBeInTheDocument()
  })

  it('polls every 8 s while disconnected', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fetch.mockResolvedValue(response({ requests: [] }))
    const live = fakeRealtime({ connected: false })
    render(<RequestCount />, { wrapper: live.wrapper })
    await screen.findByText('0 requests')
    await idle(16000)
    await waitFor(() => expect(calls('/api/requests')).toBe(3))
  })
})

describe('conversation inbox', () => {
  it('refreshes on message and request pushes without polling', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fetch.mockResolvedValue(response({ conversations: [] }))
    const live = fakeRealtime()
    render(<ConversationInbox />, { wrapper: live.wrapper })
    await screen.findByText(/No conversations yet/)
    await idle(30000)
    expect(calls('/api/conversations')).toBe(1)
    live.fire('chat_message', { request_id: 7, message: {} })
    await waitFor(() => expect(calls('/api/conversations')).toBe(2))
    live.fire('request', { request_id: 7 })
    await waitFor(() => expect(calls('/api/conversations')).toBe(3))
  })

  it('backfills on reconnect after polling while disconnected', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fetch.mockResolvedValue(response({ conversations: [] }))
    const live = fakeRealtime({ connected: false })
    render(<ConversationInbox />, { wrapper: live.wrapper })
    await screen.findByText(/No conversations yet/)
    await idle(8000)
    await waitFor(() => expect(calls('/api/conversations')).toBe(2))
    live.setConnected(true)
    await waitFor(() => expect(calls('/api/conversations')).toBe(3))
    await idle(30000)
    expect(calls('/api/conversations')).toBe(3)
  })

  it('leaves lists without pushes polling as before', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fetch.mockResolvedValue(response({ blocks: [] }))
    const live = fakeRealtime()
    render(<BlockedStudents />, { wrapper: live.wrapper })
    await waitFor(() => expect(calls('/api/blocks')).toBe(1))
    await idle(8000)
    await waitFor(() => expect(calls('/api/blocks')).toBe(2))
  })
})

describe('meeting panel', () => {
  const path = '/api/requests/7/meetings'

  it('refreshes only for its own conversation and never polls while connected', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fetch.mockResolvedValue(response({ meetings: [] }))
    const live = fakeRealtime()
    render(<MeetingPanel requestId={7} user={student} active />, {
      wrapper: live.wrapper,
    })
    await waitFor(() => expect(calls(path)).toBe(1))
    await idle(30000)
    live.fire('meeting', { request_id: 8 })
    await idle(1000)
    expect(calls(path)).toBe(1)
    live.fire('meeting', { request_id: 7 })
    await waitFor(() => expect(calls(path)).toBe(2))
  })

  it('polls every 10 s while disconnected', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fetch.mockResolvedValue(response({ meetings: [] }))
    const live = fakeRealtime({ connected: false })
    render(<MeetingPanel requestId={7} user={student} active />, {
      wrapper: live.wrapper,
    })
    await waitFor(() => expect(calls(path)).toBe(1))
    await idle(10000)
    await waitFor(() => expect(calls(path)).toBe(2))
  })
})
