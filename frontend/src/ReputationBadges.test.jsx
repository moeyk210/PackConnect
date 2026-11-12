import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ReputationBadges from './ReputationBadges'

const rated = {
  average_rating: 7.3,
  rating_count: 4,
  helpful_percent: 75,
  students_helped: 3,
  response_rate: 71,
}
const empty = {
  average_rating: null,
  rating_count: 0,
  helpful_percent: null,
  students_helped: 0,
  response_rate: null,
}

const badgeTexts = () =>
  within(screen.getByRole('list', { name: 'Advisor reputation' }))
    .getAllByRole('listitem')
    .map((item) => item.textContent)

describe('ReputationBadges', () => {
  it('shows rating, students helped and response rate on cards', () => {
    render(<ReputationBadges reputation={rated} />)
    expect(badgeTexts()).toEqual([
      '★ 7.3/10 · 4 ratings',
      '3 students helped',
      '71% response rate',
    ])
  })

  it('adds the helpful percentage on detailed profiles', () => {
    render(<ReputationBadges reputation={rated} detailed />)
    expect(badgeTexts()).toContain('75% found it helpful')
  })

  it('highlights only the rating badge', () => {
    render(<ReputationBadges reputation={rated} />)
    const [rating, ...others] = screen.getAllByRole('listitem')
    expect(rating).toHaveClass('reputation-badge', 'rated')
    for (const badge of others) expect(badge).not.toHaveClass('rated')
  })

  it('uses singular wording for one rating and one student', () => {
    render(
      <ReputationBadges
        reputation={{
          ...rated,
          average_rating: 7,
          rating_count: 1,
          students_helped: 1,
        }}
      />,
    )
    expect(badgeTexts()).toEqual([
      '★ 7.0/10 · 1 rating',
      '1 student helped',
      '71% response rate',
    ])
  })

  it('shows "No ratings yet" and hides empty stats for a new advisor', () => {
    render(<ReputationBadges reputation={empty} detailed />)
    expect(badgeTexts()).toEqual(['No ratings yet'])
    expect(screen.getByRole('listitem')).not.toHaveClass('rated')
  })

  it('shows a response rate even before any ratings', () => {
    render(
      <ReputationBadges
        reputation={{ ...empty, students_helped: 2, response_rate: 100 }}
      />,
    )
    expect(badgeTexts()).toEqual([
      'No ratings yet',
      '2 students helped',
      '100% response rate',
    ])
  })

  it('renders nothing when the API sends no reputation', () => {
    const { container } = render(<ReputationBadges reputation={undefined} />)
    expect(container).toBeEmptyDOMElement()
  })
})
