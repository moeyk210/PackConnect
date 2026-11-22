import { useEffect, useEffectEvent, useId, useRef, useState } from 'react'
import { api, json } from './messagingApi'
import './Messaging.css'
import MeetingPanel from './MeetingPanel'
import { ReportForm } from './Community'
import {
  useRealtimeConnected,
  useRealtimeEmit,
  useRealtimeEvent,
} from './realtime'
import { ConversationFeedback } from './FeedbackPanel'

export function ConnectionRequestForm({
  student,
  defaultCourse,
  onRequestCreated,
}) {
  const [form, setForm] = useState({
    course_code: defaultCourse,
    advice_topic: '',
    message: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  async function submit(event) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      await api(
        '/api/requests',
        json('POST', { ...form, recipient_id: student.id }),
      )
      setSuccess(true)
      onRequestCreated()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }
  if (success)
    return (
      <section className="request-form">
        <p className="message-success" role="status">
          Request sent to {student.name}. Chat will unlock if they accept.
        </p>
        <a href="#/app/requests">View your requests</a>
      </section>
    )
  return (
    <form className="request-form" onSubmit={submit}>
      <h3>Request advice from {student.name}</h3>
      <p className="profile-note">
        Your signed-in profile identifies you. Send some context first; private
        chat unlocks after acceptance.
      </p>
      <fieldset className="request-fields" disabled={busy}>
        <label>
          Course
          <input
            value={form.course_code}
            onChange={(e) => setForm({ ...form, course_code: e.target.value })}
            maxLength={30}
            required
            placeholder="CSC 510"
          />
        </label>
        <label>
          Advice topic
          <input
            value={form.advice_topic}
            onChange={(e) => setForm({ ...form, advice_topic: e.target.value })}
            maxLength={80}
            required
            placeholder="Projects, workload, preparation"
          />
        </label>
        <label>
          Your request
          <textarea
            value={form.message}
            onChange={(e) => setForm({ ...form, message: e.target.value })}
            maxLength={1000}
            rows={4}
            required
            placeholder="What would you like to learn from their experience?"
          />
        </label>
        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={
            !form.course_code.trim() ||
            !form.advice_topic.trim() ||
            !form.message.trim()
          }
        >
          {busy ? 'Sending...' : 'Send request'}
        </button>
      </fieldset>
    </form>
  )
}

export function RequestInbox({
  user,
  requests,
  loading,
  error,
  onRefresh,
  initialTab = 'incoming',
}) {
  const [tab, setTab] = useState(initialTab)
  const [busy, setBusy] = useState(null)
  const [actionError, setActionError] = useState('')
  async function respond(id, status) {
    if (busy !== null) return
    setBusy(id)
    setActionError('')
    try {
      await api(`/api/requests/${id}`, json('PATCH', { status }))
      await onRefresh()
    } catch (err) {
      setActionError(err.message)
    } finally {
      setBusy(null)
    }
  }
  const visible = requests.filter((item) =>
    tab === 'incoming'
      ? item.recipient_id === user.id
      : item.sender_id === user.id,
  )
  return (
    <section className="request-panel">
      <div className="section-heading">
        <div>
          <h2>Your requests</h2>
          <p>
            Accept a request to start a private conversation. Requests and
            messages are saved across visits.
          </p>
        </div>
        <button type="button" onClick={onRefresh}>
          Refresh
        </button>
      </div>
      <div className="request-tabs" aria-label="Request direction">
        <button
          type="button"
          aria-pressed={tab === 'incoming'}
          onClick={() => setTab('incoming')}
        >
          Incoming
        </button>
        <button
          type="button"
          aria-pressed={tab === 'outgoing'}
          onClick={() => setTab('outgoing')}
        >
          Outgoing
        </button>
      </div>
      {(error || actionError) && (
        <p className="error-message" role="alert">
          {actionError || error}
        </p>
      )}
      {loading ? (
        <p role="status">Loading requests...</p>
      ) : visible.length === 0 ? (
        <p className="empty-state">
          No {tab} requests yet. <a href="#/app">Find peers</a>
        </p>
      ) : (
        <div className="request-list">
          {visible.map((item) => {
            const incoming = item.recipient_id === user.id
            const peerId = incoming ? item.sender_id : item.recipient_id
            const peerName = incoming ? item.sender_name : item.recipient_name
            return (
              <article className="request-card" key={item.id}>
                <div>
                  <div className="request-card-header">
                    <a href={`#/app/students/${peerId}`}>{peerName}</a>
                    <span className={`status-badge ${item.status}`}>
                      {item.status}
                    </span>
                  </div>
                  <p>
                    <strong>{item.course_code}</strong> · {item.advice_topic}
                  </p>
                  <p className="preserve-lines">{item.message}</p>
                  <time dateTime={item.created_at}>
                    {new Date(item.created_at).toLocaleString()}
                  </time>
                </div>
                <div className="request-actions">
                  {item.status === 'pending' && incoming && (
                    <>
                      <button
                        type="button"
                        disabled={busy !== null}
                        onClick={() => respond(item.id, 'accepted')}
                      >
                        {busy === item.id ? 'Saving...' : 'Accept'}
                      </button>
                      <button
                        type="button"
                        disabled={busy !== null}
                        onClick={() => respond(item.id, 'declined')}
                      >
                        Decline
                      </button>
                    </>
                  )}
                  {item.status === 'pending' && !incoming && (
                    <>
                      <span className="profile-note">
                        Waiting for a response
                        {item.expires_at
                          ? ` · Expires ${new Date(item.expires_at).toLocaleString()}`
                          : ''}
                      </span>
                      <button
                        type="button"
                        disabled={busy !== null}
                        onClick={() => respond(item.id, 'cancelled')}
                      >
                        Cancel request
                      </button>
                    </>
                  )}
                  {['accepted', 'completed', 'closed'].includes(
                    item.status,
                  ) && (
                    <a className="chat-open" href={`#/app/chat/${item.id}`}>
                      {['completed', 'closed'].includes(item.status)
                        ? 'View message history'
                        : 'Open chat'}
                    </a>
                  )}
                  {item.status === 'accepted' && (
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={() => respond(item.id, 'completed')}
                    >
                      {busy === item.id ? 'Saving...' : 'Complete advice'}
                    </button>
                  )}
                  {item.status === 'declined' && (
                    <span className="profile-note">Chat is unavailable</span>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}

const TYPING_SIGNAL_MS = 2000
const TYPING_VISIBLE_MS = 5000
// Consecutive messages from one sender within this gap form a visual run.
const RUN_GAP_MS = 5 * 60 * 1000

function sameRun(a, b) {
  return (
    Boolean(a && b) &&
    a.sender_id === b.sender_id &&
    Math.abs(new Date(b.created_at) - new Date(a.created_at)) < RUN_GAP_MS
  )
}

function runPosition(previous, item, next) {
  const joinsPrevious = sameRun(previous, item)
  const joinsNext = sameRun(item, next)
  if (joinsPrevious && joinsNext) return 'middle'
  if (joinsPrevious) return 'last'
  if (joinsNext) return 'first'
  return 'single'
}

// A "more actions" menu button (WAI-ARIA APG menu button pattern): Enter or
// Space opens it and focuses the first item, arrows move between items,
// Escape closes it and returns focus to the button, Tab closes it.
function MessageActions({ label, actions }) {
  const [open, setOpen] = useState(false)
  const button = useRef(null)
  const menu = useRef(null)
  const buttonId = useId()
  const menuId = useId()
  useEffect(() => {
    if (!open) return undefined
    menu.current?.querySelector('[role="menuitem"]')?.focus()
    function outside(event) {
      if (
        !menu.current?.contains(event.target) &&
        !button.current?.contains(event.target)
      )
        setOpen(false)
    }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [open])
  function onMenuKeyDown(event) {
    const items = [...menu.current.querySelectorAll('[role="menuitem"]')]
    const index = items.indexOf(document.activeElement)
    const focusItem = (next) =>
      items[(next + items.length) % items.length]?.focus()
    if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
      button.current?.focus()
    } else if (event.key === 'ArrowDown') {
      event.preventDefault()
      focusItem(index + 1)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      focusItem(index - 1)
    } else if (event.key === 'Home') {
      event.preventDefault()
      focusItem(0)
    } else if (event.key === 'End') {
      event.preventDefault()
      focusItem(items.length - 1)
    } else if (event.key === 'Tab') {
      setOpen(false)
    }
  }
  return (
    <div className="message-actions">
      <button
        ref={button}
        id={buttonId}
        type="button"
        className="message-actions-button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((value) => !value)}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault()
            setOpen(true)
          }
        }}
      >
        <span aria-hidden="true">⋯</span>
      </button>
      {open && (
        <div
          ref={menu}
          id={menuId}
          role="menu"
          aria-labelledby={buttonId}
          className="message-menu"
          onKeyDown={onMenuKeyDown}
        >
          {actions.map((action) => (
            <button
              key={action.label}
              type="button"
              role="menuitem"
              tabIndex={-1}
              onClick={() => {
                setOpen(false)
                action.onSelect()
              }}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function mergeMessages(previous, incoming) {
  return [
    ...new Map([...previous, ...incoming].map((m) => [m.id, m])).values(),
  ].sort((a, b) => a.id - b.id)
}

export function Conversation({ requestId, user }) {
  const [record, setRecord] = useState(null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [sendError, setSendError] = useState('')
  const [body, setBody] = useState('')
  const [sending, setSending] = useState(false)
  const [reportedMessage, setReportedMessage] = useState(null)
  const [peerRead, setPeerRead] = useState(0)
  const log = useRef(null)
  const connected = useRealtimeConnected()
  // Only fetched rows advance the cursor. Pushed rows are merged by ID, so a
  // message missed while disconnected can never fall behind the cursor.
  const cursor = useRef({ requestId, id: 0 })
  const syncNow = useRef(null)
  useEffect(() => {
    if (cursor.current.requestId !== requestId)
      cursor.current = { requestId, id: 0 }
    const controller = new AbortController()
    let timer
    let running = false
    let again = false
    async function sync() {
      if (running) {
        again = true
        return
      }
      running = true
      clearTimeout(timer)
      try {
        let data
        do {
          data = await api(
            `/api/requests/${requestId}/messages?after_id=${cursor.current.id}`,
            { signal: controller.signal },
          )
          if (controller.signal.aborted) return
          setRecord(data.request)
          setError('')
          setPeerRead((read) => Math.max(read, data.peer_last_read_id ?? 0))
          if (data.messages.length) {
            cursor.current.id = data.messages[data.messages.length - 1].id
            setMessages((previous) => mergeMessages(previous, data.messages))
          }
        } while (data.has_more)
        setLoading(false)
        // Polling is only the fallback while the socket is down.
        if (!connected) timer = setTimeout(sync, 3000)
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err.message)
          setLoading(false)
          timer = setTimeout(sync, 5000)
        }
      } finally {
        running = false
        if (again && !controller.signal.aborted) {
          again = false
          sync()
        }
      }
    }
    syncNow.current = sync
    // Runs on open, and on every (re)connect to backfill anything missed.
    sync()
    return () => {
      controller.abort()
      clearTimeout(timer)
      syncNow.current = null
    }
  }, [requestId, connected])
  // Messages count as read only while this tab is visible; a hidden tab marks
  // them read when the student comes back.
  const unreadWhileHidden = useRef(0)
  async function markRead(messageId) {
    if (document.visibilityState !== 'visible') {
      unreadWhileHidden.current = Math.max(unreadWhileHidden.current, messageId)
      return
    }
    try {
      await api(
        `/api/requests/${requestId}/read`,
        json('POST', { through_id: messageId }),
      )
    } catch {
      // Not critical: the next history fetch records the read position too.
    }
  }
  const markReadOnReturn = useEffectEvent(() => {
    if (document.visibilityState !== 'visible' || !unreadWhileHidden.current)
      return
    const messageId = unreadWhileHidden.current
    unreadWhileHidden.current = 0
    markRead(messageId)
  })
  useEffect(() => {
    const onVisibilityChange = () => markReadOnReturn()
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () =>
      document.removeEventListener('visibilitychange', onVisibilityChange)
  }, [])
  // Typing: send at most one signal per 2 s; show the peer's for 5 s after
  // their latest signal, or until their message arrives.
  const emit = useRealtimeEmit()
  const lastTypingSignal = useRef(0)
  const [peerTyping, setPeerTyping] = useState(false)
  const peerTypingTimer = useRef(null)
  useEffect(() => () => clearTimeout(peerTypingTimer.current), [])
  function signalTyping(value) {
    const now = Date.now()
    if (!value.trim() || now - lastTypingSignal.current < TYPING_SIGNAL_MS)
      return
    if (emit('typing', { request_id: requestId }))
      lastTypingSignal.current = now
  }
  function stopPeerTyping() {
    clearTimeout(peerTypingTimer.current)
    setPeerTyping(false)
  }
  useRealtimeEvent('typing', (event) => {
    if (event.request_id !== requestId || event.user_id === user.id) return
    clearTimeout(peerTypingTimer.current)
    setPeerTyping(true)
    peerTypingTimer.current = setTimeout(stopPeerTyping, TYPING_VISIBLE_MS)
  })
  useRealtimeEvent('chat_message', (event) => {
    if (event.request_id !== requestId) return
    setMessages((previous) => mergeMessages(previous, [event.message]))
    if (event.message.sender_id !== user.id) {
      stopPeerTyping()
      markRead(event.message.id)
    }
  })
  useRealtimeEvent('request', (event) => {
    if (event.request_id === requestId) syncNow.current?.() // status changed
  })
  useRealtimeEvent('read', (event) => {
    if (event.request_id === requestId && event.reader_id !== user.id)
      setPeerRead((read) => Math.max(read, event.last_read_id))
  })
  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight
  }, [messages.length])
  async function send(event) {
    event.preventDefault()
    if (sending || !body.trim()) return
    setSending(true)
    setSendError('')
    try {
      const data = await api(
        `/api/requests/${requestId}/messages`,
        json('POST', { body }),
      )
      setMessages((previous) => mergeMessages(previous, [data.message]))
      setBody('')
    } catch (err) {
      setSendError(err.message)
    } finally {
      setSending(false)
    }
  }
  const peerName =
    record &&
    (record.sender_id === user.id ? record.recipient_name : record.sender_name)
  // "Seen" belongs on the student's own latest message only.
  const lastOwnId = messages.reduce(
    (latest, item) => (item.sender_id === user.id ? item.id : latest),
    0,
  )
  return (
    <section className="conversation">
      <a className="profile-back" href="#/app/requests">
        Back to requests
      </a>
      <header className="conversation-heading">
        <h2>{peerName ? `Chat with ${peerName}` : 'Conversation'}</h2>
        {record && (
          <p>
            {record.course_code} · {record.advice_topic}{' '}
            <span className={`status-badge ${record.status}`}>
              {['completed', 'closed'].includes(record.status)
                ? 'Closed'
                : 'Connected'}
            </span>
          </p>
        )}
      </header>
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      {loading && <p role="status">Loading conversation...</p>}
      {record && (
        <>
          <MeetingPanel
            key={requestId}
            requestId={requestId}
            user={user}
            active={
              record.status === 'accepted' && record.contact_allowed !== false
            }
          />
          {reportedMessage && (
            <ReportForm
              studentId={reportedMessage.sender_id}
              messageId={reportedMessage.id}
              onClose={() => setReportedMessage(null)}
            />
          )}
          <p className="conversation-context">
            <strong>Original request:</strong> {record.message}
          </p>
          <div
            className="chat-log"
            role="log"
            aria-label="Conversation messages"
            aria-live="polite"
            ref={log}
          >
            {messages.length === 0 ? (
              <p className="empty-state">You're connected. Say hello!</p>
            ) : (
              messages.map((item, index) => {
                const own = item.sender_id === user.id
                const position = runPosition(
                  messages[index - 1],
                  item,
                  messages[index + 1],
                )
                const endsRun = position === 'last' || position === 'single'
                const sent = new Date(item.created_at)
                return (
                  <article
                    className={`chat-row ${own ? 'own' : 'peer'} ${position}`}
                    key={item.id}
                  >
                    <div className="chat-bubble">
                      {/* Names are implied by side in a two-person chat;
                          screen readers still hear who sent each message. */}
                      <span className="visually-hidden">
                        {own ? 'You sent' : `${peerName} sent`}
                      </span>
                      <p>{item.body}</p>
                    </div>
                    {!own && (
                      <MessageActions
                        label={`More actions for message from ${peerName}`}
                        actions={[
                          {
                            label: 'Report message',
                            onSelect: () => setReportedMessage(item),
                          },
                        ]}
                      />
                    )}
                    {endsRun && (
                      <p className="chat-meta">
                        <time
                          dateTime={item.created_at}
                          title={sent.toLocaleString()}
                        >
                          {sent.toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </time>
                        {item.id === lastOwnId && lastOwnId <= peerRead && (
                          <span className="chat-seen">Seen</span>
                        )}
                      </p>
                    )}
                  </article>
                )
              })
            )}
          </div>
          <p className="typing-indicator" aria-live="polite">
            {peerTyping && peerName ? `${peerName} is typing…` : ''}
          </p>
          <ConversationFeedback
            requestId={requestId}
            record={record}
            messages={messages}
            peerName={peerName}
          />
          {['completed', 'closed'].includes(record.status) ||
          record.contact_allowed === false ? (
            <p role="status">
              {record.status === 'closed' || record.contact_allowed === false
                ? 'This connection is closed. Message history is read-only. Contact controls are available on the student’s profile.'
                : 'This advice is complete. Message history is read-only. You can send a new request from the advisor’s profile when they are available.'}
            </p>
          ) : (
            <>
              <p className="profile-note">
                Finished? Use Complete advice in{' '}
                <a href="#/app/requests">Requests</a> to free an advisor slot.
              </p>
              <form className="chat-compose" onSubmit={send}>
                <label htmlFor="chat-message">Message to {peerName}</label>
                <textarea
                  id="chat-message"
                  value={body}
                  onChange={(e) => {
                    setBody(e.target.value)
                    signalTyping(e.target.value)
                  }}
                  onKeyDown={(e) => {
                    // Enter sends and Shift+Enter adds a line. Enter that
                    // confirms an input-method composition (e.g. Japanese
                    // or Chinese input) must not send a half-typed message.
                    if (
                      e.key === 'Enter' &&
                      !e.shiftKey &&
                      !e.nativeEvent.isComposing
                    ) {
                      e.preventDefault()
                      e.currentTarget.form.requestSubmit()
                    }
                  }}
                  maxLength={2000}
                  rows={3}
                  placeholder="Write a message..."
                  disabled={sending}
                  required
                />
                <div>
                  <span>
                    {body.length}/2000 · Enter to send, Shift+Enter for a new
                    line
                  </span>
                  <button type="submit" disabled={sending || !body.trim()}>
                    {sending ? 'Sending...' : 'Send message'}
                  </button>
                </div>
                {sendError && (
                  <p className="error-message" role="alert">
                    {sendError}
                  </p>
                )}
              </form>
            </>
          )}
        </>
      )}
    </section>
  )
}
