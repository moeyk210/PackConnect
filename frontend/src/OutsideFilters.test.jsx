import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import OutsideFilters from './OutsideFilters'
import { student } from './test/fixtures'

const advisors = ['Ana', 'Ben', 'Cal', 'Dee', 'Eli'].map((name, index) => ({
  ...student,
  id: index + 1,
  name,
}))

const shownNames = () =>
  screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent)

describe('OutsideFilters', () => {
  it('shows three students at a time and flips with the arrows', async () => {
    render(<OutsideFilters students={advisors} />)
    expect(shownNames()).toEqual(['Ana', 'Ben', 'Cal'])
    expect(screen.getByText('Showing 1–3 of 5')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Previous students' }),
    ).toBeDisabled()

    await userEvent.click(screen.getByRole('button', { name: 'Next students' }))

    // The last view fills all three places instead of showing a lone card.
    expect(shownNames()).toEqual(['Cal', 'Dee', 'Eli'])
    expect(screen.getByText('Showing 3–5 of 5')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next students' })).toBeDisabled()

    await userEvent.click(
      screen.getByRole('button', { name: 'Previous students' }),
    )
    expect(shownNames()).toEqual(['Ana', 'Ben', 'Cal'])
  })

  it('shows nothing when there are no students outside the filters', () => {
    const { container } = render(<OutsideFilters students={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
