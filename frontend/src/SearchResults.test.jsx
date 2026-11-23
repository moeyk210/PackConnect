import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import SearchResults from './SearchResults'
import { emptyResults, readSearchResults } from './searchResponse'
import { student } from './test/fixtures'

const advisor = (id, name, extra = {}) => ({
  ...student,
  id,
  name,
  match_reasons: [],
  missed_filters: [],
  ...extra,
})

function renderResults(results, props = {}) {
  render(
    <SearchResults
      results={{ ...emptyResults, ...results }}
      loading={false}
      onPageChange={vi.fn()}
      {...props}
    />,
  )
}

describe('readSearchResults', () => {
  it('reads matches, near misses, totals and paging', () => {
    const results = readSearchResults({
      students: [advisor(1, 'Zoe')],
      outside_filters: [advisor(2, 'Kai')],
      total_matches: 1,
      total_outside_filters: 4,
      limit: 20,
      offset: 0,
    })
    expect(results.totalOutside).toBe(4)
    expect(results.outside.map((row) => row.name)).toEqual(['Kai'])
  })

  it('still accepts the older plain list of matches', () => {
    const results = readSearchResults([advisor(1, 'Zoe')])
    expect(results.totalMatches).toBe(1)
    expect(results.outside).toEqual([])
  })
})

describe('SearchResults', () => {
  it('highlights the best fit on the first page and keeps ranked order', () => {
    renderResults({
      matches: [advisor(1, 'Zoe'), advisor(2, 'Maya'), advisor(3, 'Aaron')],
      totalMatches: 3,
    })
    const topMatch = screen.getByText('⭐ Top match').parentElement
    expect(
      within(topMatch).getByRole('heading', { name: 'Zoe' }),
    ).toBeInTheDocument()
    expect(
      screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent),
    ).toEqual(['Zoe', 'Maya', 'Aaron'])
  })

  it('does not call the first card on a later page the top match', () => {
    renderResults({
      matches: [advisor(21, 'Ben')],
      totalMatches: 21,
      offset: 20,
    })
    expect(screen.queryByText('⭐ Top match')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Ben' })).toBeInTheDocument()
  })

  it('lists near misses under Outside your filters', () => {
    renderResults({
      matches: [advisor(1, 'Zoe')],
      outside: [advisor(2, 'Kai')],
      totalMatches: 1,
      totalOutside: 1,
    })
    const outside = screen
      .getByRole('heading', { name: 'Outside your filters' })
      .closest('.outside-filters')
    expect(
      within(outside).getByRole('heading', { name: 'Kai' }),
    ).toBeInTheDocument()
  })

  it('explains when only near misses were found', () => {
    renderResults({ outside: [advisor(2, 'Kai')], totalOutside: 1 })
    expect(
      screen.getByText(
        'No exact matches. Here are students outside your filters.',
      ),
    ).toBeInTheDocument()
  })

  it('reports page changes', async () => {
    const onPageChange = vi.fn()
    renderResults(
      {
        matches: [advisor(1, 'Zoe')],
        totalMatches: 45,
      },
      { onPageChange },
    )
    await userEvent.click(screen.getByRole('button', { name: 'Page 2' }))
    expect(onPageChange).toHaveBeenCalledWith(20)
  })
})
