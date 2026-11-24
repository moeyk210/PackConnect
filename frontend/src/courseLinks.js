// Course pages live at #/app/courses/<code>. Codes contain a space, so they are
// URL-encoded; the course page decodes them and the API normalizes them.
export const courseHref = (code) =>
  `#/app/courses/${encodeURIComponent(code.trim())}`
