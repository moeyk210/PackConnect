import './Pagination.css'
import { pageNumbers } from './pageNumbers'

// Previous / page numbers / Next. Pages are worked out from the result count,
// the page size (limit) and how many results come before this page (offset).
export default function Pagination({ total, limit, offset, onPageChange }) {
  const totalPages = Math.ceil(total / limit)
  if (totalPages <= 1) return null
  const current = Math.floor(offset / limit) + 1
  const goTo = (page) => onPageChange((page - 1) * limit)

  return (
    <nav className="pagination" aria-label="Result pages">
      <button
        type="button"
        onClick={() => goTo(current - 1)}
        disabled={current === 1}
      >
        ‹ Previous
      </button>
      {pageNumbers(current, totalPages).map((page, index) =>
        page === '…' ? (
          <span key={`gap-${index}`} className="pagination-gap">
            …
          </span>
        ) : (
          <button
            key={page}
            type="button"
            onClick={() => goTo(page)}
            aria-current={page === current ? 'page' : undefined}
            aria-label={`Page ${page}`}
          >
            {page}
          </button>
        ),
      )}
      <button
        type="button"
        onClick={() => goTo(current + 1)}
        disabled={current === totalPages}
      >
        Next ›
      </button>
    </nav>
  )
}
