import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import CoursePage from './CoursePage'
import { courseHref } from './courseLinks'
import { response } from './test/fixtures'

const advisor = (id, name, extra = {}) => ({
  id,
  name,
  program: 'MS Computer Science',
  year: 'Second Year',
  reputation: {
    average_rating: 9,
    rating_count: 5,
    helpful_percent: 90,
    students_helped: 4,
    response_rate: 100,
  },
  ...extra,
})

const page = (extra = {}) => ({
  course: {
    code: 'CSC 510',
    title: 'Software Engineering',
    description: 'Teams build a real product.',
  },
  advisors: [advisor(2, 'Alex Morgan'), advisor(3, 'Sam Lee')],
  ratings: {
    min_ratings: 3,
    workload: { average: 3.4, count: 5 },
    difficulty: { average: 4.1, count: 7 },
  },
  ...extra,
})

describe('course page', () => {
  it('shows the title, description, ratings and advisors for a course', async () => {
    fetch.mockResolvedValue(response(page()))
    render(<CoursePage code="CSC 510" />)

    expect(
      await screen.findByRole('heading', {
        name: 'CSC 510 Software Engineering',
      }),
    ).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/courses/CSC%20510', {
      signal: expect.any(AbortSignal),
    })
    expect(screen.getByText('Teams build a real product.')).toBeVisible()
    expect(screen.getByText('3.4')).toBeInTheDocument()
    expect(screen.getByText('4.1')).toBeInTheDocument()
    expect(screen.getByText(/5 students/)).toBeInTheDocument()
    expect(screen.getByText(/7 students/)).toBeInTheDocument()
  })

  it('lists the advisors in the order the API ranked them, linked to their profiles', async () => {
    fetch.mockResolvedValue(response(page()))
    render(<CoursePage code="CSC 510" />)

    const alex = await screen.findByRole('link', { name: 'Alex Morgan' })
    const sam = screen.getByRole('link', { name: 'Sam Lee' })
    expect(alex).toHaveAttribute('href', '#/app/students/2')
    expect(sam).toHaveAttribute('href', '#/app/students/3')
    expect(
      alex.compareDocumentPosition(sam) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(
      screen.getAllByRole('list', { name: 'Advisor reputation' }),
    ).toHaveLength(2)
  })

  it('hides averages that do not have enough ratings yet', async () => {
    fetch.mockResolvedValue(
      response(
        page({ ratings: { min_ratings: 3, workload: null, difficulty: null } }),
      ),
    )
    render(<CoursePage code="CSC 510" />)

    expect(
      await screen.findByText(/at least 3 students who took this course/),
    ).toBeInTheDocument()
    expect(screen.queryByText('Workload')).not.toBeInTheDocument()
  })

  it('shows one average when only that one has enough ratings', async () => {
    fetch.mockResolvedValue(
      response(
        page({
          ratings: {
            min_ratings: 3,
            workload: { average: 2, count: 3 },
            difficulty: null,
          },
        }),
      ),
    )
    render(<CoursePage code="CSC 510" />)

    expect(await screen.findByText('2.0')).toBeInTheDocument()
    expect(screen.getByText('Not enough ratings yet')).toBeInTheDocument()
  })

  it('says so when a course has no description or no available advisors', async () => {
    fetch.mockResolvedValue(
      response(
        page({
          course: { code: 'CSC 540', title: 'Databases', description: '' },
          advisors: [],
        }),
      ),
    )
    render(<CoursePage code="CSC 540" />)

    expect(
      await screen.findByText('No description has been added yet.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('No available advisors have completed this course yet.'),
    ).toBeInTheDocument()
  })

  it('shows a not-found state for a code that is not in the catalog', async () => {
    fetch.mockResolvedValue(response({ error: 'Course not found.' }, 404))
    render(<CoursePage code="CSC 999" />)

    expect(
      await screen.findByRole('heading', { name: 'Course not found' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/CSC 999 is not in the course catalog/),
    ).toBeVisible()
    expect(
      screen.getByRole('link', { name: 'Back to Find peers' }),
    ).toHaveAttribute('href', '#/app')
  })

  it('shows an error, not a not-found page, when the request fails', async () => {
    fetch.mockResolvedValue(response({}, 500))
    render(<CoursePage code="CSC 510" />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not load this course',
    )
    expect(screen.queryByText('Course not found')).not.toBeInTheDocument()
  })

  it('shows a loading message first', () => {
    fetch.mockReturnValue(new Promise(() => {}))
    render(<CoursePage code="CSC 510" />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading course...')
  })
})

describe('course links', () => {
  it('encode the code so it fits in the address', () => {
    expect(courseHref('CSC 510')).toBe('#/app/courses/CSC%20510')
    expect(courseHref(' csc-510 ')).toBe('#/app/courses/csc-510')
  })
})
