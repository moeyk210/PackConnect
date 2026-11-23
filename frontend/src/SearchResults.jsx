import OutsideFilters from './OutsideFilters'
import Pagination from './Pagination'
import StudentCard from './StudentCard'
import './SearchResults.css'

const studentCount = (count) => `${count} student${count === 1 ? '' : 's'}`

// The ranked search results: "Your matches" (best fit first, with the top one
// highlighted on the first page) and their page numbers, then a fixed
// "Outside your filters" row that stays the same on every page.
export default function SearchResults({ results, loading, onPageChange }) {
  const { matches, outside, totalMatches, limit, offset } = results
  const nothingFound = matches.length === 0 && outside.length === 0
  const [topMatch, ...otherMatches] =
    offset === 0 ? matches : [null, ...matches]

  return (
    <section className="results">
      <div className="section-heading">
        <div>
          <h3>Students who can help</h3>
          <p>Connect with peers who have experience in your course.</p>
        </div>
        <span className="result-count">{studentCount(totalMatches)}</span>
      </div>

      {loading ? (
        <p className="empty-state">Searching for students...</p>
      ) : nothingFound ? (
        <p className="empty-state">
          No students found. Try another course code.
        </p>
      ) : (
        <>
          {totalMatches === 0 && (
            <p className="empty-state">
              No exact matches. Here are students outside your filters.
            </p>
          )}

          {topMatch && (
            <div className="top-match">
              <span className="top-match-label">⭐ Top match</span>
              <StudentCard student={topMatch} />
            </div>
          )}

          {otherMatches.length > 0 && (
            <div className="student-grid">
              {otherMatches.map((student) => (
                <StudentCard key={student.id} student={student} />
              ))}
            </div>
          )}

          <Pagination
            total={totalMatches}
            limit={limit}
            offset={offset}
            onPageChange={onPageChange}
          />

          {/* A new set of near misses starts again from the first card. */}
          <OutsideFilters
            key={outside.map((student) => student.id).join(',')}
            students={outside}
          />
        </>
      )}
    </section>
  )
}
