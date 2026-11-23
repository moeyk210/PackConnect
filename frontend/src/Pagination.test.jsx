import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Pagination from './Pagination'
import { pageNumbers } from './pageNumbers'

describe('pageNumbers', () => {
  it('lists every page when there are only a few', () => {
    expect(pageNumbers(1, 3)).toEqual([1, 2, 3])
  })

  it('shortens long lists around the current page', () => {
    expect(pageNumbers(6, 12)).toEqual([1, '…', 5, 6, 7, '…', 12])
    expect(pageNumbers(1, 12)).toEqual([1, 2, '…', 12])
    expect(pageNumbers(12, 12)).toEqual([1, '…', 11, 12])
  })
})

describe('Pagination', () => {
  it('shows nothing when everything fits on one page', () => {
    const { container } = render(
      <Pagination total={12} limit={20} offset={0} onPageChange={vi.fn()} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('marks the current page and turns page clicks into offsets', async () => {
    const onPageChange = vi.fn()
    render(
      <Pagination
        total={45}
        limit={20}
        offset={20}
        onPageChange={onPageChange}
      />,
    )
    expect(screen.getByRole('button', { name: 'Page 2' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Page 3' }))
    expect(onPageChange).toHaveBeenLastCalledWith(40)
    await userEvent.click(screen.getByRole('button', { name: '‹ Previous' }))
    expect(onPageChange).toHaveBeenLastCalledWith(0)
  })

  it('disables Previous on the first page and Next on the last', () => {
    const { rerender } = render(
      <Pagination total={45} limit={20} offset={0} onPageChange={vi.fn()} />,
    )
    expect(screen.getByRole('button', { name: '‹ Previous' })).toBeDisabled()
    rerender(
      <Pagination total={45} limit={20} offset={40} onPageChange={vi.fn()} />,
    )
    expect(screen.getByRole('button', { name: 'Next ›' })).toBeDisabled()
  })
})
