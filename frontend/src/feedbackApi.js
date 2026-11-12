import { api, json } from './messagingApi'

// Keep these in step with backend/features/feedback.py.
export const MIN_RATING = 1
export const MAX_RATING = 10
export const MAX_COMMENT_LENGTH = 500

const feedbackPath = (requestId) => `/api/requests/${requestId}/feedback`

// Resolves to { feedback, can_rate }; feedback is null until you have rated.
export function getFeedback(requestId, options = {}) {
  return api(feedbackPath(requestId), options)
}

// Resolves to the stored feedback; rejects with the API's error message.
export async function submitFeedback(requestId, { rating, helpful, comment }) {
  const data = await api(
    feedbackPath(requestId),
    json('POST', { rating, helpful, comment: comment.trim() }),
  )
  return data.feedback
}

// Returns an error message for the form, or '' when the draft can be sent.
export function validateFeedback({ rating, helpful, comment }) {
  if (!Number.isInteger(rating) || rating < MIN_RATING || rating > MAX_RATING)
    return `Choose a rating from ${MIN_RATING} to ${MAX_RATING}.`
  if (typeof helpful !== 'boolean') return 'Say whether the advice was helpful.'
  if (comment.trim().length > MAX_COMMENT_LENGTH)
    return `Keep your comment to ${MAX_COMMENT_LENGTH} characters or fewer.`
  return ''
}
