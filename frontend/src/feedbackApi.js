import { api, json } from './messagingApi'

// Keep these in step with backend/features/feedback.py.
export const MIN_RATING = 1
export const MAX_RATING = 10
export const MAX_COMMENT_LENGTH = 500

// Optional ratings of the course.
export const MIN_COURSE_RATING = 1
export const MAX_COURSE_RATING = 5

const feedbackPath = (requestId) => `/api/requests/${requestId}/feedback`

// Resolves to { feedback, can_rate }; feedback is null until you have rated.
export function getFeedback(requestId, options = {}) {
  return api(feedbackPath(requestId), options)
}

// Resolves to the stored feedback; rejects with the API's error message.
export async function submitFeedback(
  requestId,
  { rating, helpful, comment, workload_rating, difficulty_rating },
) {
  const body = { rating, helpful, comment: comment.trim() }
  // The course ratings are optional, so they are only sent when chosen.
  if (workload_rating != null) body.workload_rating = workload_rating
  if (difficulty_rating != null) body.difficulty_rating = difficulty_rating
  const data = await api(feedbackPath(requestId), json('POST', body))
  return data.feedback
}

const validCourseRating = (value) =>
  value == null ||
  (Number.isInteger(value) &&
    value >= MIN_COURSE_RATING &&
    value <= MAX_COURSE_RATING)

// Returns an error message for the form, or '' when the draft can be sent.
export function validateFeedback({
  rating,
  helpful,
  comment,
  workload_rating,
  difficulty_rating,
}) {
  if (!Number.isInteger(rating) || rating < MIN_RATING || rating > MAX_RATING)
    return `Choose a rating from ${MIN_RATING} to ${MAX_RATING}.`
  if (typeof helpful !== 'boolean') return 'Say whether the advice was helpful.'
  if (comment.trim().length > MAX_COMMENT_LENGTH)
    return `Keep your comment to ${MAX_COMMENT_LENGTH} characters or fewer.`
  if (
    !validCourseRating(workload_rating) ||
    !validCourseRating(difficulty_rating)
  )
    return `Course ratings must be from ${MIN_COURSE_RATING} to ${MAX_COURSE_RATING}.`
  return ''
}
