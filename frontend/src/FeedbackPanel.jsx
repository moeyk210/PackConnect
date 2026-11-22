import { useEffect, useState } from 'react'
import {
  MAX_COMMENT_LENGTH,
  MAX_RATING,
  MIN_RATING,
  getFeedback,
  submitFeedback,
  validateFeedback,
} from './feedbackApi'
import './Messaging.css'
import './FeedbackPanel.css'

const RATINGS = Array.from(
  { length: MAX_RATING - MIN_RATING + 1 },
  (_, index) => MIN_RATING + index,
)

// Read-only record of the feedback the signed-in person gave.
export function FeedbackSummary({ feedback }) {
  return (
    <section className="feedback-panel" aria-labelledby="feedback-heading">
      <h3 id="feedback-heading">Your feedback</h3>
      <p className="feedback-summary">
        <strong>
          {feedback.rating}/{MAX_RATING}
        </strong>
        <span
          className={`status-badge ${feedback.helpful ? 'accepted' : 'declined'}`}
        >
          {feedback.helpful ? 'Helpful' : 'Not helpful'}
        </span>
      </p>
      {feedback.comment && (
        <p className="conversation-context">{feedback.comment}</p>
      )}
      <p className="profile-note">
        Thanks. Feedback can't be changed after it's sent.
      </p>
    </section>
  )
}

export default function FeedbackPanel({
  requestId,
  peerName,
  feedback,
  onSubmitted,
}) {
  const [draft, setDraft] = useState({
    rating: null,
    helpful: null,
    comment: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (feedback) return <FeedbackSummary feedback={feedback} />

  async function submit(event) {
    event.preventDefault()
    if (busy) return
    const problem = validateFeedback(draft)
    if (problem) {
      setError(problem)
      return
    }
    setBusy(true)
    setError('')
    try {
      onSubmitted(await submitFeedback(requestId, draft))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="feedback-panel" aria-labelledby="feedback-heading">
      <h3 id="feedback-heading">Rate this conversation</h3>
      <p className="profile-note">
        How was your conversation with {peerName}? You can send feedback once.
      </p>
      <form onSubmit={submit} noValidate>
        <fieldset className="request-fields" disabled={busy}>
          <div className="feedback-question">
            <span id="rating-label">Rating</span>
            <div
              className="feedback-options"
              role="group"
              aria-labelledby="rating-label"
            >
              {RATINGS.map((rating) => (
                <button
                  type="button"
                  key={rating}
                  aria-pressed={draft.rating === rating}
                  aria-label={`${rating} out of ${MAX_RATING}`}
                  onClick={() => setDraft({ ...draft, rating })}
                >
                  {rating}
                </button>
              ))}
            </div>
          </div>
          <div className="feedback-question">
            <span id="helpful-label">Was the advice helpful?</span>
            <div
              className="feedback-options"
              role="group"
              aria-labelledby="helpful-label"
            >
              {[
                [true, 'Yes'],
                [false, 'No'],
              ].map(([helpful, label]) => (
                <button
                  type="button"
                  key={label}
                  aria-pressed={draft.helpful === helpful}
                  onClick={() => setDraft({ ...draft, helpful })}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <label>
            Comment (optional)
            <textarea
              value={draft.comment}
              onChange={(e) => setDraft({ ...draft, comment: e.target.value })}
              maxLength={MAX_COMMENT_LENGTH}
              rows={3}
              placeholder="What made this advice useful, or what was missing?"
            />
          </label>
          <p className="feedback-count">
            {draft.comment.length}/{MAX_COMMENT_LENGTH}
          </p>
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="feedback-submit">
            {busy ? 'Sending...' : 'Send feedback'}
          </button>
        </fieldset>
      </form>
    </section>
  )
}

const RATEABLE_STATUSES = ['accepted', 'completed']

// Chat-view wrapper: loads feedback state once both people have messaged, then
// shows the form while rating is open, or the summary once feedback is given.
export function ConversationFeedback({
  requestId,
  record,
  messages,
  peerName,
}) {
  const [state, setState] = useState(null)
  const bothMessaged =
    messages.some((item) => item.sender_id === record.sender_id) &&
    messages.some((item) => item.sender_id === record.recipient_id)
  const relevant = bothMessaged && RATEABLE_STATUSES.includes(record.status)

  useEffect(() => {
    if (!relevant) return undefined
    const controller = new AbortController()
    getFeedback(requestId, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setState(data)
      })
      .catch(() => {
        // Feedback is secondary to the chat: if it cannot load, stay hidden.
        if (!controller.signal.aborted) setState(null)
      })
    return () => controller.abort()
  }, [requestId, relevant])

  if (!relevant || !state || (!state.feedback && !state.can_rate)) return null
  return (
    <FeedbackPanel
      requestId={requestId}
      peerName={peerName}
      feedback={state.feedback}
      onSubmitted={(feedback) => setState({ feedback, can_rate: false })}
    />
  )
}
