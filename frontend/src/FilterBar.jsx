import { useEffect, useId, useRef, useState } from 'react'
import './FilterBar.css'

// Text filters: each pill opens a small box to type a value.
const TEXT_FILTERS = [
  { key: 'program', label: 'Program', placeholder: 'e.g. MS Computer Science' },
  { key: 'year', label: 'Year', placeholder: 'e.g. Second Year' },
  { key: 'skills', label: 'Skills', placeholder: 'e.g. React, Python' },
  {
    key: 'advice_topics',
    label: 'Advice topics',
    placeholder: 'e.g. Interview prep',
  },
]

// On/off filters: each pill switches its filter with one click.
const TOGGLE_FILTERS = [
  { key: 'availableOnly', label: 'Available only' },
  { key: 'includeUnrated', label: 'New advisors (no reviews)' },
]

// The small box for typing a filter value. It is created fresh each time it
// opens, so it always starts from the value currently applied.
function FilterPopover({ filter, value, onClose, onApply }) {
  const [draft, setDraft] = useState(value)
  const inputId = useId()
  const apply = (nextValue) => {
    onApply(nextValue.trim())
    onClose()
  }

  return (
    <div
      className="filter-popover"
      role="dialog"
      aria-label={`${filter.label} filter`}
    >
      <label htmlFor={inputId}>{filter.label}</label>
      <input
        id={inputId}
        value={draft}
        placeholder={filter.placeholder}
        autoFocus
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') apply(draft)
          if (event.key === 'Escape') onClose()
        }}
      />
      <div className="filter-popover-actions">
        <button type="button" className="filter-link" onClick={() => apply('')}>
          Clear
        </button>
        <button
          type="button"
          className="filter-apply"
          onClick={() => apply(draft)}
        >
          Apply
        </button>
      </div>
    </div>
  )
}

// One text filter: a pill showing its current value, which opens the box above.
function TextFilterPill({ filter, value, open, onOpen, onClose, onApply }) {
  const wrapRef = useRef(null)

  // Close the box when the student clicks anywhere else.
  useEffect(() => {
    if (!open) return undefined
    const closeOnOutsideClick = (event) => {
      if (!wrapRef.current?.contains(event.target)) onClose()
    }
    document.addEventListener('mousedown', closeOnOutsideClick)
    return () => document.removeEventListener('mousedown', closeOnOutsideClick)
  }, [open, onClose])

  return (
    <div className="filter-pill-wrap" ref={wrapRef}>
      <button
        type="button"
        className={value ? 'filter-pill active' : 'filter-pill'}
        aria-expanded={open}
        onClick={open ? onClose : onOpen}
      >
        <span className="filter-pill-text">
          {value ? `${filter.label}: ${value}` : filter.label}
        </span>
        <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <FilterPopover
          filter={filter}
          value={value}
          onClose={onClose}
          onApply={onApply}
        />
      )}
    </div>
  )
}

// A row of filter pills under the search box. Each change is applied at once
// through onApply, so results update without pressing Find Students again.
export default function FilterBar({ filters, defaults, onApply, onClearAll }) {
  const [openKey, setOpenKey] = useState(null)
  const changed = Object.keys(defaults).some(
    (key) => filters[key] !== defaults[key],
  )

  return (
    <div className="filter-bar" aria-label="Search filters" role="group">
      {TEXT_FILTERS.map((filter) => (
        <TextFilterPill
          key={filter.key}
          filter={filter}
          value={filters[filter.key]}
          open={openKey === filter.key}
          onOpen={() => setOpenKey(filter.key)}
          onClose={() => setOpenKey(null)}
          onApply={(value) => onApply({ ...filters, [filter.key]: value })}
        />
      ))}
      {TOGGLE_FILTERS.map((filter) => (
        <button
          key={filter.key}
          type="button"
          className={filters[filter.key] ? 'filter-pill active' : 'filter-pill'}
          aria-pressed={filters[filter.key]}
          onClick={() =>
            onApply({ ...filters, [filter.key]: !filters[filter.key] })
          }
        >
          {filters[filter.key] && <span aria-hidden="true">✓</span>}
          {filter.label}
        </button>
      ))}
      {changed && (
        <button type="button" className="filter-link" onClick={onClearAll}>
          Clear all
        </button>
      )}
    </div>
  )
}
