import { useEffect, useId, useRef, useState } from 'react'
import './CourseAutocomplete.css'

// In "multiple" mode the field holds a comma-separated list. Only the part
// after the last comma is looked up, and choosing a suggestion replaces just
// that part.
function splitList(value, multiple) {
  if (!multiple) return { head: '', tail: value }
  const cut = value.lastIndexOf(',')
  return { head: value.slice(0, cut + 1), tail: value.slice(cut + 1) }
}

function isCourse(course) {
  return typeof course?.code === 'string' && typeof course?.title === 'string'
}

export default function CourseAutocomplete({
  value,
  onChange,
  multiple = false,
  inputId,
  label = 'Course code',
  placeholder = 'Enter a course code, e.g. CSC 510',
  hint,
  maxLength,
}) {
  const id = useId()
  const list = useRef(null)
  const [focused, setFocused] = useState(false)
  const [dismissed, setDismissed] = useState(false)
  const [result, setResult] = useState({
    query: '',
    courses: [],
    failed: false,
  })
  const [active, setActive] = useState(-1)
  const { head, tail } = splitList(value, multiple)
  const query = tail.trim()
  const current = result.query === query
  const courses = current ? result.courses : []
  const open = focused && !dismissed && Boolean(query)
  const hintText =
    hint ??
    (multiple
      ? 'Separate courses with commas. Suggestions come from the course catalog; you can also type any code.'
      : 'Suggestions come from the course catalog. You can also enter a code.')
  const announcement =
    open && courses.length
      ? `${courses.length} suggestion${courses.length === 1 ? '' : 's'} available. Use the up and down arrow keys to review them and Enter to select.`
      : ''

  useEffect(() => {
    if (open && active >= 0) {
      list.current?.children[active]?.scrollIntoView?.({ block: 'nearest' })
    }
  }, [open, active])

  useEffect(() => {
    if (!focused || dismissed || !query) return
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(
          `/api/courses?q=${encodeURIComponent(query)}`,
          {
            signal: controller.signal,
          },
        )
        if (!response.ok) throw new Error('Unable to load courses')
        const data = await response.json()
        if (!Array.isArray(data?.courses) || !data.courses.every(isCourse)) {
          throw new Error('Invalid course suggestions')
        }
        if (!controller.signal.aborted) {
          setResult({ query, courses: data.courses, failed: false })
        }
      } catch {
        if (!controller.signal.aborted) {
          setResult({ query, courses: [], failed: true })
        }
      }
    }, 200)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query, focused, dismissed])

  function select(code) {
    const spacer = head ? ' ' : ''
    onChange(multiple ? `${head}${spacer}${code}, ` : code)
    setDismissed(true)
    setActive(-1)
  }

  return (
    <div className="course-autocomplete">
      <div className="course-input-wrap">
        <input
          id={inputId}
          type="text"
          role="combobox"
          aria-label={inputId ? undefined : label}
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={open ? `${id}-list` : undefined}
          aria-activedescendant={
            open && courses[active] ? `${id}-${active}` : undefined
          }
          aria-describedby={`${id}-hint`}
          autoComplete="off"
          maxLength={maxLength ?? (multiple ? undefined : 30)}
          value={value}
          placeholder={placeholder}
          onChange={(event) => {
            onChange(event.target.value)
            setActive(-1)
            setDismissed(false)
          }}
          onFocus={() => {
            setFocused(true)
            // A filled list should not pop open just because it was focused.
            setDismissed(multiple)
          }}
          onBlur={() => {
            setFocused(false)
            setActive(-1)
          }}
          onKeyDown={(event) => {
            if (event.nativeEvent.isComposing) return
            if (event.key === 'Escape') {
              event.preventDefault()
              setDismissed(true)
              setActive(-1)
            } else if (['ArrowDown', 'ArrowUp'].includes(event.key)) {
              event.preventDefault()
              setDismissed(false)
              if (courses.length) {
                setActive((previous) =>
                  event.key === 'ArrowDown'
                    ? (previous + 1) % courses.length
                    : (previous <= 0 ? courses.length : previous) - 1,
                )
              }
            } else if (event.key === 'Enter' && open && courses[active]) {
              event.preventDefault()
              select(courses[active].code)
            } else if (event.key === 'Enter') {
              setDismissed(true)
            }
          }}
        />
        {open && (
          <div className="course-suggestions">
            <ul
              ref={list}
              role="listbox"
              aria-label={`${label} suggestions`}
              id={`${id}-list`}
            >
              {courses.map((course, index) => (
                <li
                  key={course.code}
                  id={`${id}-${index}`}
                  role="option"
                  aria-selected={index === active}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => select(course.code)}
                >
                  <span className="course-code">{course.code}</span>{' '}
                  <span className="course-title">{course.title}</span>
                </li>
              ))}
            </ul>
            {!courses.length && (
              <p role="status">
                {!current
                  ? 'Looking up courses…'
                  : result.failed
                    ? 'Suggestions unavailable. You can still search by course code.'
                    : 'No matching courses yet. You can still search by course code.'}
              </p>
            )}
          </div>
        )}
      </div>
      <span className="course-hint" id={`${id}-hint`}>
        {hintText}
      </span>
      <div className="course-sr-only" aria-live="polite" aria-atomic="true">
        {announcement}
      </div>
    </div>
  )
}
