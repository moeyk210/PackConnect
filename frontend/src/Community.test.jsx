import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import {
  ConversationInbox,
  ReportForm,
  SafetyControls,
  Moderation,
} from './Community'
import MeetingPanel from './MeetingPanel'
import PasswordRecovery from './PasswordRecovery'
import { response, student } from './test/fixtures'

it('shows private conversation previews, unread counts, and links', async () => {
  fetch.mockResolvedValue(
    response({
      conversations: [
        {
          id: 7,
          peer_name: 'Sam Lee',
          course_code: 'CSC 510',
          advice_topic: 'Projects',
          latest_message: 'Some advice',
          unread_count: 2,
          status: 'accepted',
          updated_at: '2026-10-29T12:00:00Z',
        },
      ],
    }),
  )
  render(<ConversationInbox />)
  const row = await screen.findByRole('link', { name: /Sam Lee/ })
  expect(row).toHaveAttribute('href', '#/app/chat/7')
  expect(row).toHaveClass('unread')
  expect(screen.getByText('Some advice')).toBeInTheDocument()
  expect(screen.getByText('2 unread')).toHaveClass('visually-hidden')
  expect(screen.getByText('SL')).toHaveAttribute('aria-hidden', 'true')
})

it('labels inbox times like a messaging app and caps large unread counts', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date(2026, 10, 18, 15) })
  const conversation = (id, peer_name, updated, extra = {}) => ({
    id,
    peer_name,
    course_code: 'CSC 510',
    advice_topic: 'Projects',
    latest_message: 'Hi',
    unread_count: 0,
    status: 'accepted',
    updated_at: updated.toISOString(),
    ...extra,
  })
  fetch.mockResolvedValue(
    response({
      conversations: [
        conversation(1, 'Today Person', new Date(2026, 10, 18, 9, 5), {
          unread_count: 150,
        }),
        conversation(2, 'Yesterday Person', new Date(2026, 10, 17, 23, 0)),
        conversation(3, 'Week Person', new Date(2026, 10, 14, 12, 0)),
        conversation(4, 'Old Person', new Date(2026, 9, 3, 12, 0), {
          status: 'completed',
        }),
        conversation(5, 'Last Year', new Date(2025, 0, 2, 12, 0)),
      ],
    }),
  )
  try {
    render(<ConversationInbox />)
    const row = async (name) =>
      within(await screen.findByRole('link', { name: new RegExp(name) }))
    const time = (date, options) => date.toLocaleDateString([], options)
    expect(
      (await row('Today Person')).getByText(
        new Date(2026, 10, 18, 9, 5).toLocaleTimeString([], {
          hour: 'numeric',
          minute: '2-digit',
        }),
      ),
    ).toBeInTheDocument()
    expect((await row('Today Person')).getByText('99+')).toBeInTheDocument()
    expect(
      (await row('Today Person')).getByText('150 unread'),
    ).toBeInTheDocument()
    expect(
      (await row('Yesterday Person')).getByText('Yesterday'),
    ).toBeInTheDocument()
    expect(
      (await row('Week Person')).getByText(
        time(new Date(2026, 10, 14), { weekday: 'short' }),
      ),
    ).toBeInTheDocument()
    const old = await row('Old Person')
    expect(
      old.getByText(
        time(new Date(2026, 9, 3), { month: 'short', day: 'numeric' }),
      ),
    ).toBeInTheDocument()
    expect(old.getByText(/completed/)).toBeInTheDocument()
    expect((await row('Week Person')).queryByText(/accepted/)).toBeNull()
    expect(
      (await row('Last Year')).getByText(
        time(new Date(2025, 0, 2), {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
        }),
      ),
    ).toBeInTheDocument()
  } finally {
    vi.useRealTimers()
  }
})

it('submits a report with the selected message as evidence', async () => {
  const user = userEvent.setup()
  fetch.mockResolvedValue(response({ report_id: 3 }, 201))
  render(<ReportForm studentId={2} messageId={9} onClose={() => {}} />)
  await user.type(
    screen.getByRole('textbox', { name: 'Report reason' }),
    'Unwanted contact',
  )
  await user.click(screen.getByRole('button', { name: 'Submit report' }))
  expect(fetch).toHaveBeenCalledWith(
    '/api/students/2/reports',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ reason: 'Unwanted contact', message_id: 9 }),
    }),
  )
  expect(await screen.findByRole('status')).toHaveTextContent(
    'moderator review',
  )
})

it('blocks a student and refreshes the contact controls', async () => {
  const user = userEvent.setup()
  const changed = vi.fn()
  fetch.mockResolvedValue(response({ status: 'ok' }))
  render(<SafetyControls student={{ ...student, id: 2 }} onChanged={changed} />)
  await user.click(screen.getByRole('button', { name: 'Block student' }))
  expect(fetch).toHaveBeenCalledWith(
    '/api/students/2/block',
    expect.objectContaining({ method: 'POST' }),
  )
  await waitFor(() => expect(changed).toHaveBeenCalledTimes(1))
})

it('shows moderator permission failures instead of exposing report data', async () => {
  fetch.mockResolvedValue(
    response({ error: 'Moderator access required.' }, 403),
  )
  render(<Moderation />)
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Moderator access required',
  )
})

it('sends a time-zone-aware meeting proposal', async () => {
  const user = userEvent.setup()
  fetch.mockImplementation((url, options) =>
    Promise.resolve(
      response(
        options?.method === 'POST' ? { meeting: { id: 1 } } : { meetings: [] },
      ),
    ),
  )
  render(<MeetingPanel requestId={7} user={student} active />)
  fireEvent.change(screen.getByLabelText('Meeting date and time'), {
    target: { value: '2026-11-02T14:30' },
  })
  await user.type(screen.getByLabelText('Meeting location or link'), 'Library')
  await user.click(screen.getByRole('button', { name: 'Propose meeting' }))
  const write = fetch.mock.calls.find(
    ([, options]) => options?.method === 'POST',
  )
  expect(write[0]).toBe('/api/requests/7/meetings')
  const payload = JSON.parse(write[1].body)
  expect(payload.starts_at).toBe(new Date('2026-11-02T14:30').toISOString())
  expect(new Date(payload.ends_at) - new Date(payload.starts_at)).toBe(
    30 * 60000,
  )
  expect(payload.location).toBe('Library')
})

it('lets the other participant accept a proposal and download the calendar event', async () => {
  const user = userEvent.setup()
  let status = 'proposed'
  fetch.mockImplementation((url, options) => {
    if (options?.method === 'PATCH') {
      status = 'accepted'
      return Promise.resolve(response({ status }))
    }
    return Promise.resolve(
      response({
        meetings: [
          {
            id: 8,
            proposer_id: 2,
            starts_at: '2026-11-02T14:30:00Z',
            ends_at: '2026-11-02T15:00:00Z',
            location: 'Online',
            status,
          },
        ],
      }),
    )
  })
  render(<MeetingPanel requestId={7} user={student} active />)
  await user.click(
    await screen.findByRole('button', { name: 'Accept meeting' }),
  )
  expect(
    await screen.findByRole('link', { name: 'Download calendar event' }),
  ).toHaveAttribute('href', '/api/requests/7/meetings/8/calendar.ics')
})

it('requests a recovery email without exposing account existence', async () => {
  const user = userEvent.setup()
  fetch.mockResolvedValue(
    response({
      message: 'If an eligible account exists, a recovery email will be sent.',
    }),
  )
  render(<PasswordRecovery route="forgot-password" />)
  await user.type(
    screen.getByLabelText('Recovery email address'),
    'student@example.test',
  )
  await user.click(screen.getByRole('button', { name: 'Send recovery link' }))
  expect(fetch).toHaveBeenCalledWith(
    '/api/auth/forgot-password',
    expect.objectContaining({
      body: JSON.stringify({ email: 'student@example.test' }),
    }),
  )
  expect(await screen.findByRole('status')).toHaveTextContent(
    'If an eligible account exists',
  )
})

it('validates matching passwords before redeeming the recovery token', async () => {
  const user = userEvent.setup()
  const reset = vi.fn()
  fetch.mockResolvedValue(response({ message: 'Password updated.' }))
  render(
    <PasswordRecovery
      route={'reset-password?token=' + 'x'.repeat(43)}
      onReset={reset}
    />,
  )
  await user.type(screen.getByLabelText('New password'), 'a new long password')
  await user.type(
    screen.getByLabelText('Confirm new password'),
    'a wrong long password',
  )
  await user.click(screen.getByRole('button', { name: 'Reset password' }))
  expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match')
  expect(fetch).not.toHaveBeenCalled()
  await user.clear(screen.getByLabelText('Confirm new password'))
  await user.type(
    screen.getByLabelText('Confirm new password'),
    'a new long password',
  )
  await user.click(screen.getByRole('button', { name: 'Reset password' }))
  await waitFor(() => expect(reset).toHaveBeenCalledTimes(1))
})
