// Deterministic feedback API data for frontend tests.
export const givenFeedback = {
  id: 3,
  request_id: 7,
  rating: 8,
  helpful: true,
  comment: 'Clear project tips.',
  created_at: '2026-01-02T12:00:00Z',
}

export const notRatedYet = { feedback: null, can_rate: true }
export const notOpenYet = { feedback: null, can_rate: false }
export const alreadyRated = { feedback: givenFeedback, can_rate: false }
