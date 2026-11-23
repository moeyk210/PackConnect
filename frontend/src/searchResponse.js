// Shape of the search results the page shows when nothing has been searched yet.
export const emptyResults = {
  matches: [],
  outside: [],
  totalMatches: 0,
  totalOutside: 0,
  limit: 20,
  offset: 0,
}

// Read a /api/students/search response into the shape the page uses.
// "matches" meet every filter; "outside" are near misses shown below them.
// Older responses were a plain list of matches, so that shape still works.
export function readSearchResults(data) {
  if (Array.isArray(data)) {
    return { ...emptyResults, matches: data, totalMatches: data.length }
  }
  const matches = data.students ?? []
  const outside = data.outside_filters ?? []
  return {
    matches,
    outside,
    totalMatches: data.total_matches ?? matches.length,
    totalOutside: data.total_outside_filters ?? outside.length,
    limit: data.limit ?? emptyResults.limit,
    offset: data.offset ?? 0,
  }
}
