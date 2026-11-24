import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import FeedbackPanel from './FeedbackPanel'
import { deferred, response } from './test/fixtures'
import { givenFeedback } from './test/feedbackFixtures'

function renderPanel(props = {}) {
  const onSubmitted = vi.fn()
  render(
    <FeedbackPanel
      requestId={7}
      peerName="Alex Morgan"
      feedback={null}
      onSubmitted={onSubmitted}
      {...props}
    />,
  )
  return { onSubmitted, user: userEvent.setup() }
}

const ratingGroup = () => screen.getByRole('group', { name: 'Rating' })
const helpfulGroup = () =>
  screen.getByRole('group', { name: 'Was the advice helpful?' })

describe('FeedbackPanel', () => {
  it('offers ratings from 1 to 10 and a helpful choice', () => {
    renderPanel()
    expect(
      screen.getByRole('heading', { name: 'Rate this conversation' }),
    ).toBeInTheDocument()
    expect(within(ratingGroup()).getAllByRole('button')).toHaveLength(10)
    expect(
      within(ratingGroup()).getByRole('button', { name: '10 out of 10' }),
    ).toBeInTheDocument()
    expect(within(helpfulGroup()).getAllByRole('button')).toHaveLength(2)
  })

  it('marks the chosen rating and helpful answer as pressed', async () => {
    const { user } = renderPanel()
    const seven = screen.getByRole('button', { name: '7 out of 10' })
    await user.click(seven)
    expect(seven).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: '9 out of 10' }))
    expect(seven).toHaveAttribute('aria-pressed', 'false')
    const no = within(helpfulGroup()).getByRole('button', { name: 'No' })
    await user.click(no)
    expect(no).toHaveAttribute('aria-pressed', 'true')
  })

  it('requires a rating before sending', async () => {
    const { user, onSubmitted } = renderPanel()
    await user.click(screen.getByRole('button', { name: 'Send feedback' }))
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Choose a rating from 1 to 10.',
    )
    expect(fetch).not.toHaveBeenCalled()
    expect(onSubmitted).not.toHaveBeenCalled()
  })

  it('requires a helpful answer before sending', async () => {
    const { user } = renderPanel()
    await user.click(screen.getByRole('button', { name: '8 out of 10' }))
    await user.click(screen.getByRole('button', { name: 'Send feedback' }))
    expect(screen.getByRole('alert')).toHaveTextContent('helpful')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('limits the comment to 500 characters and shows a count', async () => {
    const { user } = renderPanel()
    const comment = screen.getByLabelText('Comment (optional)')
    expect(comment).toHaveAttribute('maxLength', '500')
    await user.type(comment, 'Great tips')
    expect(screen.getByText('10/500')).toBeInTheDocument()
  })

  it('submits the feedback and reports what was stored', async () => {
    const pending = deferred()
    fetch.mockReturnValue(pending.promise)
    const { user, onSubmitted } = renderPanel()
    await user.click(screen.getByRole('button', { name: '8 out of 10' }))
    await user.click(screen.getByRole('button', { name: 'Yes' }))
    await user.type(
      screen.getByLabelText('Comment (optional)'),
      'Clear project tips.',
    )
    await user.click(screen.getByRole('button', { name: 'Send feedback' }))

    expect(screen.getByRole('button', { name: 'Sending...' })).toBeDisabled()
    const [url, options] = fetch.mock.calls[0]
    expect(url).toBe('/api/requests/7/feedback')
    expect(JSON.parse(options.body)).toEqual({
      rating: 8,
      helpful: true,
      comment: 'Clear project tips.',
    })
    pending.resolve(response({ feedback: givenFeedback }, 201))
    await vi.waitFor(() =>
      expect(onSubmitted).toHaveBeenCalledWith(givenFeedback),
    )
  })

  it('shows the API error and lets the person try again', async () => {
    fetch.mockResolvedValueOnce(
      response(
        { error: 'Feedback opens after you have both sent a message.' },
        403,
      ),
    )
    const { user, onSubmitted } = renderPanel()
    await user.click(screen.getByRole('button', { name: '6 out of 10' }))
    await user.click(screen.getByRole('button', { name: 'No' }))
    await user.click(screen.getByRole('button', { name: 'Send feedback' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Feedback opens after you have both sent a message.',
    )
    expect(onSubmitted).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Send feedback' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '6 out of 10' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('shows a read-only summary when feedback was already given', () => {
    renderPanel({ feedback: givenFeedback })
    expect(
      screen.getByRole('heading', { name: 'Your feedback' }),
    ).toBeInTheDocument()
    expect(screen.getByText('8/10')).toBeInTheDocument()
    expect(screen.getByText('Helpful')).toBeInTheDocument()
    expect(screen.getByText('Clear project tips.')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('summarises unhelpful feedback without a comment', () => {
    renderPanel({ feedback: { ...givenFeedback, helpful: false, comment: '' } })
    expect(screen.getByText('Not helpful')).toBeInTheDocument()
    expect(screen.queryByText('Clear project tips.')).not.toBeInTheDocument()
  })

  it('offers optional 1 to 5 workload and difficulty ratings', async () => {
    const { user } = renderPanel({ courseCode: 'CSC 510' })
    const workload = screen.getByRole('group', {
      name: 'Course workload (optional)',
    })
    expect(within(workload).getAllByRole('button')).toHaveLength(5)
    expect(
      screen.getByRole('group', { name: 'Course difficulty (optional)' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/rate CSC 510 itself/)).toBeInTheDocument()

    const four = within(workload).getByRole('button', { name: '4 out of 5' })
    await user.click(four)
    expect(four).toHaveAttribute('aria-pressed', 'true')
    await user.click(four)
    expect(four).toHaveAttribute('aria-pressed', 'false')
  })

  it('sends the course ratings only when they were chosen', async () => {
    fetch.mockResolvedValue(response({ feedback: givenFeedback }, 201))
    const { user } = renderPanel()
    await user.click(screen.getByRole('button', { name: '8 out of 10' }))
    await user.click(screen.getByRole('button', { name: 'Yes' }))
    const workload = screen.getByRole('group', {
      name: 'Course workload (optional)',
    })
    await user.click(
      within(workload).getByRole('button', { name: '2 out of 5' }),
    )
    await user.click(screen.getByRole('button', { name: 'Send feedback' }))

    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
      rating: 8,
      helpful: true,
      comment: '',
      workload_rating: 2,
    })
  })

  it('shows the course ratings in the read-only summary', () => {
    renderPanel({
      feedback: { ...givenFeedback, workload_rating: 4, difficulty_rating: 2 },
    })
    expect(
      screen.getByText('Workload 4/5 · Difficulty 2/5'),
    ).toBeInTheDocument()
  })
})
