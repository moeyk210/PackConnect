// Which page numbers to show. Short lists show every page; long ones show the
// first, last and nearby pages, with "…" for the gaps, like most shopping sites.
export function pageNumbers(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1)
  const shown = new Set([1, total, current - 1, current, current + 1])
  const pages = [...shown]
    .filter((page) => page >= 1 && page <= total)
    .sort((a, b) => a - b)
  const withGaps = []
  pages.forEach((page, index) => {
    if (index > 0 && page - pages[index - 1] > 1) withGaps.push('…')
    withGaps.push(page)
  })
  return withGaps
}
