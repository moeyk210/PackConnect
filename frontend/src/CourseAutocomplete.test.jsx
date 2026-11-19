import { useState } from 'react'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import CourseAutocomplete from './CourseAutocomplete'
import { deferred, response } from './test/fixtures'

const course = (code, title = `Title of ${code}`) => ({ code, title })
const named = (code) => new RegExp(`^${code}`)

function Search({ onSubmit = () => {}, initialValue = '', ...props }) {
  const [value, setValue] = useState(initialValue)
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit(value)
      }}
    >
      <CourseAutocomplete value={value} onChange={setValue} {...props} />
      <button>Search</button>
    </form>
  )
}

describe('course autocomplete', () => {
  it('keeps keyboard-highlighted options visible in a long suggestion list', async () => {
    fetch.mockResolvedValue(
      response({
        courses: Array.from({ length: 10 }, (_, i) => course(`CSC ${510 + i}`)),
      }),
    )
    const user = userEvent.setup()
    render(<Search />)
    await user.type(screen.getByRole('combobox'), 'CSC')
    const last = await screen.findByRole('option', { name: named('CSC 519') })
    last.scrollIntoView = vi.fn()
    await user.keyboard('{ArrowUp}')
    expect(last).toHaveAttribute('aria-selected', 'true')
    expect(last.scrollIntoView).toHaveBeenCalledWith({ block: 'nearest' })
    await user.keyboard('{ArrowDown}')
    expect(
      screen.getByRole('option', { name: named('CSC 510') }),
    ).toHaveAttribute('aria-selected', 'true')
  })

  it.each([
    {},
    { courses: null },
    { courses: [510] },
    { courses: ['CSC 510'] },
    { courses: [{ code: 'CSC 510' }] },
  ])(
    'handles malformed suggestion data without interrupting manual search: %j',
    async (data) => {
      fetch.mockResolvedValue(response(data))
      const user = userEvent.setup()
      const submit = vi.fn()
      render(<Search onSubmit={submit} />)
      await user.type(screen.getByRole('combobox'), 'CSC510')
      expect(
        await screen.findByText(
          'Suggestions unavailable. You can still search by course code.',
        ),
      ).toBeInTheDocument()
      await user.keyboard('{Enter}')
      expect(submit).toHaveBeenCalledWith('CSC510')
    },
  )

  it('selects with arrows and Enter without prematurely submitting the search', async () => {
    fetch.mockResolvedValue(
      response({ courses: [course('CSC 510'), course('CSC 540')] }),
    )
    const submit = vi.fn()
    const user = userEvent.setup()
    render(<Search onSubmit={submit} />)
    const input = screen.getByRole('combobox')
    await user.type(input, 'csc')
    await screen.findByRole('option', { name: named('CSC 510') })
    await user.keyboard('{ArrowDown}{ArrowDown}')
    const second = screen.getByRole('option', { name: named('CSC 540') })
    expect(second).toHaveAttribute('aria-selected', 'true')
    expect(input).toHaveAttribute('aria-activedescendant', second.id)
    await user.keyboard('{Enter}')
    expect(input).toHaveValue('CSC 540')
    expect(input).toHaveAttribute('aria-expanded', 'false')
    expect(submit).not.toHaveBeenCalled()
    await user.keyboard('{Enter}')
    expect(submit).toHaveBeenCalledWith('CSC 540')
  })

  it('supports pointer selection and dismisses on Escape or blur', async () => {
    fetch.mockResolvedValue(response({ courses: [course('CSC 510')] }))
    const user = userEvent.setup()
    render(<Search />)
    const input = screen.getByRole('combobox')
    await user.type(input, 'CSC')
    await user.click(
      await screen.findByRole('option', { name: named('CSC 510') }),
    )
    expect(input).toHaveValue('CSC 510')
    expect(input).toHaveFocus()
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    await user.type(input, ' ')
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    await user.keyboard('{ArrowDown}')
    expect(screen.getByRole('listbox')).toBeInTheDocument()
    await user.tab()
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it.each(['empty', 'failure'])(
    'preserves manual searches when suggestions are %s',
    async (state) => {
      fetch.mockResolvedValue(
        state === 'empty' ? response({ courses: [] }) : response({}, 503),
      )
      const user = userEvent.setup()
      const submit = vi.fn()
      render(<Search onSubmit={submit} />)
      await user.type(screen.getByRole('combobox'), 'XYZ999')
      expect(
        await screen.findByText(/You can still search by course code/),
      ).toBeInTheDocument()
      await user.keyboard('{Enter}')
      expect(submit).toHaveBeenCalledWith('XYZ999')
    },
  )

  it('debounces queries and ignores stale responses after typing or clearing', async () => {
    vi.useFakeTimers()
    try {
      const old = deferred()
      fetch
        .mockReturnValueOnce(old.promise)
        .mockResolvedValue(response({ courses: [course('ECE 200')] }))
      render(<Search />)
      const input = screen.getByRole('combobox')
      fireEvent.focus(input)
      fireEvent.change(input, { target: { value: 'C' } })
      fireEvent.change(input, { target: { value: 'CSC' } })
      expect(fetch).not.toHaveBeenCalled()
      await act(() => vi.advanceTimersByTimeAsync(200))
      expect(fetch).toHaveBeenCalledTimes(1)
      const signal = fetch.mock.calls[0][1].signal
      fireEvent.change(input, { target: { value: 'ECE' } })
      expect(signal.aborted).toBe(true)
      await act(() => vi.advanceTimersByTimeAsync(200))
      expect(
        screen.getByRole('option', { name: named('ECE 200') }),
      ).toBeInTheDocument()
      await act(async () =>
        old.resolve(response({ courses: [course('CSC 510')] })),
      )
      expect(
        screen.queryByRole('option', { name: named('CSC 510') }),
      ).not.toBeInTheDocument()
      fireEvent.change(input, { target: { value: '' } })
      await act(() => vi.advanceTimersByTimeAsync(300))
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
      expect(fetch).toHaveBeenCalledTimes(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('aborts pending suggestions when unmounted', async () => {
    fetch.mockReturnValue(deferred().promise)
    const user = userEvent.setup()
    const { unmount } = render(<Search />)
    await user.type(screen.getByRole('combobox'), 'CSC')
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
    const signal = fetch.mock.calls[0][1].signal
    unmount()
    expect(signal.aborted).toBe(true)
  })

  it('shows each course title and announces how many suggestions there are', async () => {
    fetch.mockResolvedValue(
      response({
        courses: [
          course('CSC 510', 'Software Engineering'),
          course('CSC 540', 'Database Management Concepts and Systems'),
        ],
      }),
    )
    const user = userEvent.setup()
    render(<Search />)
    await user.type(screen.getByRole('combobox'), 'csc')
    expect(
      await screen.findByRole('option', {
        name: /^CSC 510\s+Software Engineering$/,
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('option', {
        name: /^CSC 540\s+Database Management Concepts and Systems$/,
      }),
    ).toBeInTheDocument()
    expect(screen.getByText(/^2 suggestions available/)).toBeInTheDocument()
  })

  it('announces a single suggestion in the singular', async () => {
    fetch.mockResolvedValue(response({ courses: [course('CSC 510')] }))
    const user = userEvent.setup()
    render(<Search />)
    await user.type(screen.getByRole('combobox'), 'csc 510')
    expect(
      await screen.findByText(/^1 suggestion available/),
    ).toBeInTheDocument()
  })

  it('does not look anything up for a blank query', async () => {
    vi.useFakeTimers()
    try {
      render(<Search />)
      const input = screen.getByRole('combobox')
      fireEvent.focus(input)
      fireEvent.change(input, { target: { value: '   ' } })
      await act(() => vi.advanceTimersByTimeAsync(400))
      expect(fetch).not.toHaveBeenCalled()
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('exposes a labelled combobox, description and listbox to screen readers', async () => {
    fetch.mockResolvedValue(response({ courses: [course('CSC 510')] }))
    const user = userEvent.setup()
    render(<Search />)
    const input = screen.getByRole('combobox', { name: 'Course code' })
    expect(input).toHaveAttribute('aria-autocomplete', 'list')
    expect(input).toHaveAttribute('aria-expanded', 'false')
    expect(input).toHaveAccessibleDescription(/course catalog/)
    await user.type(input, 'csc')
    const listbox = await screen.findByRole('listbox', {
      name: 'Course code suggestions',
    })
    expect(input).toHaveAttribute('aria-expanded', 'true')
    expect(input).toHaveAttribute('aria-controls', listbox.id)
  })

  it('uses a visible label instead of an aria-label when one is linked', () => {
    render(
      <>
        <label htmlFor="completed-courses">Completed courses</label>
        <Search
          inputId="completed-courses"
          label="Completed courses"
          multiple
        />
      </>,
    )
    const input = screen.getByRole('combobox', { name: 'Completed courses' })
    expect(input).toHaveAttribute('id', 'completed-courses')
    expect(input).not.toHaveAttribute('aria-label')
  })

  it('suggests for the course being typed in a comma-separated list', async () => {
    fetch.mockResolvedValue(
      response({ courses: [course('CSC 510'), course('CSC 540')] }),
    )
    const user = userEvent.setup()
    render(<Search multiple />)
    const input = screen.getByRole('combobox')
    await user.type(input, 'CSC 515, csc5')
    await screen.findByRole('option', { name: named('CSC 540') })
    expect(fetch).toHaveBeenLastCalledWith(
      '/api/courses?q=csc5',
      expect.anything(),
    )
    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}')
    expect(input).toHaveValue('CSC 515, CSC 540, ')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('does not open suggestions just because a filled list was focused', async () => {
    vi.useFakeTimers()
    try {
      fetch.mockResolvedValue(response({ courses: [course('CSC 540')] }))
      render(<Search multiple initialValue="CSC 510, CSC 540" />)
      const input = screen.getByRole('combobox')
      fireEvent.focus(input)
      await act(() => vi.advanceTimersByTimeAsync(400))
      expect(fetch).not.toHaveBeenCalled()
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
      fireEvent.keyDown(input, { key: 'ArrowDown' })
      await act(() => vi.advanceTimersByTimeAsync(200))
      expect(screen.getByRole('listbox')).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('does not cap a comma-separated list at the single-code length', async () => {
    const user = userEvent.setup()
    render(<Search multiple />)
    const input = screen.getByRole('combobox')
    expect(input).not.toHaveAttribute('maxlength')
    const text = 'CSC 510, '.repeat(6)
    fetch.mockResolvedValue(response({ courses: [] }))
    await user.type(input, text)
    expect(input).toHaveValue(text)
  })
})
