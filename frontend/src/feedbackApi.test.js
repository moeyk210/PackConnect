import { describe, expect, it } from 'vitest'
import {
  MAX_COMMENT_LENGTH,
  getFeedback,
  submitFeedback,
  validateFeedback,
} from './feedbackApi'
import { response } from './test/fixtures'
import { alreadyRated, givenFeedback } from './test/feedbackFixtures'

const draft = { rating: 8, helpful: true, comment: '' }

describe('feedback API helpers', () => {
  it('loads feedback state for a request', async () => {
    fetch.mockResolvedValue(response(alreadyRated))
    await expect(getFeedback(7)).resolves.toEqual(alreadyRated)
    expect(fetch).toHaveBeenCalledWith('/api/requests/7/feedback', {})
  })

  it('submits trimmed feedback as JSON and returns what was stored', async () => {
    fetch.mockResolvedValue(response({ feedback: givenFeedback }, 201))
    await expect(
      submitFeedback(7, { rating: 8, helpful: true, comment: '  Tips.  ' }),
    ).resolves.toEqual(givenFeedback)
    const [url, options] = fetch.mock.calls[0]
    expect(url).toBe('/api/requests/7/feedback')
    expect(options.method).toBe('POST')
    expect(options.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(options.body)).toEqual({
      rating: 8,
      helpful: true,
      comment: 'Tips.',
    })
  })

  it('surfaces the API error message', async () => {
    fetch.mockResolvedValue(
      response(
        { error: 'You have already given feedback for this conversation.' },
        409,
      ),
    )
    await expect(submitFeedback(7, draft)).rejects.toThrow(
      'You have already given feedback for this conversation.',
    )
  })

  it('reports an unreachable service', async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => {
        throw new SyntaxError('not JSON')
      },
    })
    await expect(getFeedback(7)).rejects.toThrow('Could not reach')
  })
})

describe('validateFeedback', () => {
  it('accepts a complete draft, including the rating boundaries', () => {
    for (const rating of [1, 10])
      expect(validateFeedback({ ...draft, rating })).toBe('')
    expect(validateFeedback({ ...draft, helpful: false })).toBe('')
  })

  it('rejects missing or out-of-range ratings', () => {
    for (const rating of [null, 0, 11, 7.5, '8'])
      expect(validateFeedback({ ...draft, rating })).toMatch(
        'rating from 1 to 10',
      )
  })

  it('requires a helpful answer', () => {
    expect(validateFeedback({ ...draft, helpful: null })).toMatch('helpful')
  })

  it('limits the trimmed comment length', () => {
    const atLimit = `  ${'x'.repeat(MAX_COMMENT_LENGTH)}  `
    expect(validateFeedback({ ...draft, comment: atLimit })).toBe('')
    expect(
      validateFeedback({
        ...draft,
        comment: 'x'.repeat(MAX_COMMENT_LENGTH + 1),
      }),
    ).toMatch('500 characters')
  })
})
