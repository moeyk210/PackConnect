# Course autocomplete

Course fields suggest courses from the course catalog (the `courses` table,
loaded by `backend/import_catalog.py`). They appear in three places:

- the **search bar** on Find peers, which takes one course;
- the **profile editor**, for the completed and current course lists;
- the **registration form**, for the completed course list.

The profile and registration course fields are comma-separated. Suggestions
apply to the course being typed after the last comma, and choosing one replaces
only that entry and adds `, ` ready for the next. The catalog only contains the
departments that have been imported, so a code with no suggestion can still be
typed by hand. Codes are normalized to the form `CSC 510` when they are saved.

## API

`GET /api/courses?q=data` returns up to ten catalog courses as
`{"courses": [{"code": "CSC 316", "title": "Data Structures and Algorithms"}]}`.
No sign-in is needed.

- Codes match by prefix and ignore case, spaces and hyphens, so `csc5`,
  `CSC 5` and `csc-5` all find `CSC 5xx`.
- Titles match anywhere in the title, ignoring case.
- Results are ordered: an exact code, then codes that start with the query, then
  titles that start with it, then other title matches. Ties are broken by code.
- The query is matched as literal text. `%`, `_` and SQL fragments have no
  special meaning.
- A missing, blank or punctuation-only query, or one longer than 100 characters,
  returns `{"courses": []}`.

## Behavior and accessibility

The field waits 200 ms after typing before requesting suggestions and cancels
outdated requests. Nothing is requested for a blank entry.

- Arrow keys highlight options (wrapping at the ends) and scroll them into view.
  Enter selects the highlighted option without submitting the form; Enter again
  submits. Escape, blur or selection closes the list.
- In a comma-separated field the list does not open just because the field was
  focused; it opens when you type or press an arrow key.
- Manual entry always works, including when there is no match, the request
  fails or the response is invalid.
- The input is a labelled `combobox` with `aria-expanded`, `aria-controls` and
  `aria-activedescendant`, and the options are in a labelled `listbox`. Fields
  with a visible `<label>` use it as their name; the search bar uses
  "Course code".
- A visually hidden live region announces how many suggestions are available,
  and the list shows a status message while loading, when nothing matches and on
  failure.

## Automated verification

From `frontend/`, run `npm test`, `npm run lint`, `npm run build`, and
`npx prettier --check "src/**/*.{js,jsx,ts,tsx,css,json}"`.

From the repository root, run the backend suite with a dedicated local database
as described in [Supabase verification](SUPABASE.md#verification).

Backend tests (`test_course_autocomplete.py`) cover code and title matching,
ranking, the ten-result limit, blank and overlong queries, literal handling of
wildcard characters and SQL, and the fact that suggestions come from the catalog
rather than from student profiles. Frontend tests cover keyboard selection,
scrolling, mouse selection, Escape and blur, malformed and failed responses,
debouncing and cancellation, titles and screen-reader labels and announcements,
comma-separated entry, and the search, profile and registration flows.

## Browser acceptance check

Use the catalog imported with `python backend/import_catalog.py`.

1. On Find peers, type `soft`; confirm suggestions show codes with titles.
2. Use ArrowUp to highlight the last suggestion; confirm it scrolls into view.
3. Press Enter to select it, then Enter again to search.
4. Search a manual code such as `csc-510`; confirm it finds `CSC 510` peers.
5. In My profile → Edit, type `CSC 510, dat` in Completed courses; choose a
   suggestion and confirm only the last entry changed.
6. In registration, repeat step 5 for Completed courses.
7. With a screen reader or the browser's accessibility inspector, confirm the
   fields are named, the list is announced and the highlighted option is read.
8. Check that Escape and clicking elsewhere close the list, and that an unknown
   code can still be typed.
9. Repeat at a narrow mobile viewport; tap a suggestion and check that the page
   has no horizontal overflow.
