import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import FilterBar from './FilterBar'

const defaults = {
  program: '',
  year: '',
  skills: '',
  advice_topics: '',
  availableOnly: true,
  includeUnrated: true,
}

function renderBar(filters = defaults) {
  const onApply = vi.fn()
  const onClearAll = vi.fn()
  render(
    <FilterBar
      filters={filters}
      defaults={defaults}
      onApply={onApply}
      onClearAll={onClearAll}
    />,
  )
  return { onApply, onClearAll }
}

describe('FilterBar', () => {
  it('applies a typed filter from its pill', async () => {
    const user = userEvent.setup()
    const { onApply } = renderBar()
    await user.click(screen.getByRole('button', { name: /Advice topics/ }))
    await user.type(
      screen.getByRole('textbox', { name: 'Advice topics' }),
      ' interview prep ',
    )
    await user.click(screen.getByRole('button', { name: 'Apply' }))
    expect(onApply).toHaveBeenCalledWith({
      ...defaults,
      advice_topics: 'interview prep',
    })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('applies with Enter and closes with Escape without applying', async () => {
    const user = userEvent.setup()
    const { onApply } = renderBar()
    await user.click(screen.getByRole('button', { name: /Program/ }))
    await user.keyboard('Statistics{Escape}')
    expect(onApply).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: /Program/ }))
    await user.keyboard('Statistics{Enter}')
    expect(onApply).toHaveBeenCalledWith({ ...defaults, program: 'Statistics' })
  })

  it('shows the applied value on the pill and clears it', async () => {
    const user = userEvent.setup()
    const { onApply } = renderBar({ ...defaults, program: 'Statistics' })
    const pill = screen.getByRole('button', { name: /Program: Statistics/ })
    await user.click(pill)
    await user.click(screen.getByRole('button', { name: 'Clear' }))
    expect(onApply).toHaveBeenCalledWith({ ...defaults, program: '' })
  })

  it('switches on/off filters with one click', async () => {
    const user = userEvent.setup()
    const { onApply } = renderBar()
    const toggle = screen.getByRole('button', {
      name: /New advisors \(no reviews\)/,
    })
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    await user.click(toggle)
    expect(onApply).toHaveBeenCalledWith({ ...defaults, includeUnrated: false })
  })

  it('offers Clear all only when something differs from the defaults', async () => {
    const user = userEvent.setup()
    renderBar()
    expect(
      screen.queryByRole('button', { name: 'Clear all' }),
    ).not.toBeInTheDocument()
    const { onClearAll } = renderBar({ ...defaults, availableOnly: false })
    await user.click(screen.getByRole('button', { name: 'Clear all' }))
    expect(onClearAll).toHaveBeenCalled()
  })
})
