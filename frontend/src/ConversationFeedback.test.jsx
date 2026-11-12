import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Conversation } from './Messaging'
import { request, response, student } from './test/fixtures'
import {
  alreadyRated,
  givenFeedback,
  notOpenYet,
  notRatedYet,
} from './test/feedbackFixtures'

// The fixture request is from Sam Lee (id 2) to the signed-in student (id 1).
const fromSam = { id: 1, sender_id: 2, body: 'Can you help with projects?' }
const fromMe = { id: 2, sender_id: 1, body: 'Happy to help!' }

function mockChat({ status = 'accepted', messages, feedback, onFeedbackPost }) {
  fetch.mockImplementation(async (url, options = {}) => {
    if (url.startsWith('/api/requests/7/messages'))
      return response({
        request: { ...request, status },
        messages: messages.map((m) => ({
          ...m,
          created_at: request.created_at,
        })),
        has_more: false,
      })
    if (url === '/api/requests/7/meetings') return response({ meetings: [] })
    if (url === '/api/requests/7/feedback' && options.method === 'POST')
      return onFeedbackPost(JSON.parse(options.body))
    if (url === '/api/requests/7/feedback') return feedback()
    throw new Error(`Unexpected fetch: ${url}`)
  })
}

const feedbackCalls = () =>
  fetch.mock.calls.filter(([url]) => url === '/api/requests/7/feedback')

async function openChat() {
  render(<Conversation requestId={7} user={student} />)
  await screen.findByRole('heading', { name: 'Chat with Sam Lee' })
}

describe('feedback in the chat view', () => {
  it('stays hidden and does not ask the API until both people have messaged', async () => {
    mockChat({ messages: [fromSam], feedback: () => response(notRatedYet) })
    await openChat()
    expect(await screen.findByText(fromSam.body)).toBeInTheDocument()
    expect(feedbackCalls()).toHaveLength(0)
    expect(
      screen.queryByRole('heading', { name: 'Rate this conversation' }),
    ).not.toBeInTheDocument()
  })

  it('shows the form once both people have messaged', async () => {
    mockChat({
      messages: [fromSam, fromMe],
      feedback: () => response(notRatedYet),
    })
    await openChat()
    expect(
      await screen.findByRole('heading', { name: 'Rate this conversation' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/conversation with Sam Lee/)).toBeInTheDocument()
  })

  it('shows the saved summary instead of the form after a reload', async () => {
    mockChat({
      messages: [fromSam, fromMe],
      feedback: () => response(alreadyRated),
    })
    await openChat()
    expect(
      await screen.findByRole('heading', { name: 'Your feedback' }),
    ).toBeInTheDocument()
    expect(screen.getByText('8/10')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Send feedback' }),
    ).not.toBeInTheDocument()
  })

  it('keeps the summary for completed advice', async () => {
    mockChat({
      status: 'completed',
      messages: [fromSam, fromMe],
      feedback: () => response(alreadyRated),
    })
    await openChat()
    expect(
      await screen.findByRole('heading', { name: 'Your feedback' }),
    ).toBeInTheDocument()
  })

  it('stays hidden when the API says rating is not open', async () => {
    mockChat({
      messages: [fromSam, fromMe],
      feedback: () => response(notOpenYet),
    })
    await openChat()
    await screen.findByText(fromMe.body)
    await vi.waitFor(() => expect(feedbackCalls()).toHaveLength(1))
    expect(
      screen.queryByRole('heading', { name: 'Rate this conversation' }),
    ).not.toBeInTheDocument()
  })

  it('never offers rating on a closed connection', async () => {
    mockChat({
      status: 'closed',
      messages: [fromSam, fromMe],
      feedback: () => response(notRatedYet),
    })
    await openChat()
    await screen.findByText(fromMe.body)
    expect(feedbackCalls()).toHaveLength(0)
  })

  it('replaces the form with the summary after submitting', async () => {
    const user = userEvent.setup()
    const posted = []
    mockChat({
      messages: [fromSam, fromMe],
      feedback: () => response(notRatedYet),
      onFeedbackPost: (body) => {
        posted.push(body)
        return response({ feedback: { ...givenFeedback, ...body } }, 201)
      },
    })
    await openChat()
    await screen.findByRole('heading', { name: 'Rate this conversation' })
    await user.click(screen.getByRole('button', { name: '9 out of 10' }))
    await user.click(screen.getByRole('button', { name: 'Yes' }))
    await user.click(screen.getByRole('button', { name: 'Send feedback' }))

    expect(
      await screen.findByRole('heading', { name: 'Your feedback' }),
    ).toBeInTheDocument()
    expect(screen.getByText('9/10')).toBeInTheDocument()
    expect(posted).toEqual([{ rating: 9, helpful: true, comment: '' }])
    // The chat itself keeps working underneath.
    expect(
      screen.getByRole('textbox', { name: 'Message to Sam Lee' }),
    ).toBeInTheDocument()
  })

  it('leaves the chat usable if feedback cannot load', async () => {
    mockChat({
      messages: [fromSam, fromMe],
      feedback: () => response({ error: 'Server error' }, 500),
    })
    await openChat()
    await vi.waitFor(() => expect(feedbackCalls()).toHaveLength(1))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Rate this conversation' }),
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole('textbox', { name: 'Message to Sam Lee' }),
    ).toBeInTheDocument()
  })
})
