import { render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import App from './App'
import { response, student } from './test/fixtures'

const reputation = {
  average_rating: 8.5,
  rating_count: 2,
  helpful_percent: 50,
  students_helped: 2,
  response_rate: 80,
}
const ratedAdvisor = { ...student, id: 2, name: 'Rated Advisor', reputation }
const newAdvisor = {
  ...student,
  id: 3,
  name: 'New Advisor',
  reputation: {
    average_rating: null,
    rating_count: 0,
    helpful_percent: null,
    students_helped: 0,
    response_rate: null,
  },
}

beforeEach(() => {
  fetch.mockImplementation(async (url, options = {}) => {
    if (url.startsWith('/api/courses?')) return response({ courses: [] })
    if (url.startsWith('/api/students/search?'))
      return response({ students: [ratedAdvisor, newAdvisor] })
    if (url === '/api/students/2') return response({ student: ratedAdvisor })
    if (url === '/api/requests') return response({ requests: [] })
    if (url === '/api/notifications')
      return response({ notifications: [], unread_count: 0 })
    throw new Error(`Unexpected API request: ${options.method || 'GET'} ${url}`)
  })
})

const renderApp = (route) =>
  render(
    <App
      user={student}
      route={route}
      onLogout={() => {}}
      onUserUpdated={() => {}}
    />,
  )

function badgesIn(element) {
  return within(
    within(element).getByRole('list', { name: 'Advisor reputation' }),
  )
    .getAllByRole('listitem')
    .map((item) => item.textContent)
}

describe('reputation in the app', () => {
  it('shows badges on each search card, with and without ratings', async () => {
    renderApp('app')
    const rated = (
      await screen.findByRole('heading', { name: 'Rated Advisor' })
    ).closest('article')
    const fresh = screen
      .getByRole('heading', { name: 'New Advisor' })
      .closest('article')
    expect(badgesIn(rated)).toEqual([
      '★ 8.5/10 · 2 ratings',
      '2 students helped',
      '80% response rate',
    ])
    expect(badgesIn(fresh)).toEqual(['No ratings yet'])
  })

  it('shows detailed badges on the advisor profile page', async () => {
    renderApp('app/students/2')
    await screen.findByRole('heading', { name: 'Rated Advisor' })
    expect(badgesIn(document.body)).toEqual([
      '★ 8.5/10 · 2 ratings',
      '50% found it helpful',
      '2 students helped',
      '80% response rate',
    ])
  })
})
