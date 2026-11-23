import { useState } from 'react'
import StudentCard from './StudentCard'
import './OutsideFilters.css'

// How many near-miss cards are visible at once.
const CARDS_SHOWN = 3

// "Outside your filters": advisors who almost match, in one row with arrows on
// the sides. Flipping through them never changes the page of matches above.
export default function OutsideFilters({ students }) {
  const [start, setStart] = useState(0)
  if (students.length === 0) return null

  const lastStart = Math.max(0, students.length - CARDS_SHOWN)
  const first = Math.min(start, lastStart)
  const visible = students.slice(first, first + CARDS_SHOWN)

  return (
    <section className="outside-filters" aria-label="Outside your filters">
      <div className="section-heading">
        <div>
          <h3>Outside your filters</h3>
          <p>Students who took a related course or miss a filter.</p>
        </div>
      </div>

      <div className="outside-row">
        <button
          type="button"
          className="outside-arrow"
          aria-label="Previous students"
          disabled={first === 0}
          onClick={() => setStart(Math.max(0, first - CARDS_SHOWN))}
        >
          ‹
        </button>
        <div className="outside-cards">
          {visible.map((student) => (
            <StudentCard key={student.id} student={student} />
          ))}
        </div>
        <button
          type="button"
          className="outside-arrow"
          aria-label="Next students"
          disabled={first >= lastStart}
          onClick={() => setStart(Math.min(lastStart, first + CARDS_SHOWN))}
        >
          ›
        </button>
      </div>

      <p className="outside-position">
        Showing {first + 1}–{first + visible.length} of {students.length}
      </p>
    </section>
  )
}
