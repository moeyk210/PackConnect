# 07 — Project 3 delta section, badges and standard repo files

| | |
|---|---|
| **Author** | Ethan Goodman |
| **Date** | 2026-11-24 |
| **Tool / model** | Claude Code (VS Code extension), Claude Opus 5.5 |

## 1. Request

I gave the AI the Project 2 and Project 3 handouts and asked whether the repo
met every requirement. It found four gaps: `dev` was not merged into `main`,
the README did not show the delta since the fork, the inherited M0 was not
addressed, and the walk-through video was not linked. It also found that every
badge pointed to the original team's repository.

On branch `docs/project3-delta-and-repo-files`, which I created, I asked for:

1. the badges pointed at our fork;
2. a README section showing what we inherited and what we changed;
3. `INSTALL.md`;
4. a license;
5. `THIRD_PARTY_LIBRARIES.md`.

Working rules: full context and no guessing, ask me when a decision is mine,
stop after each task for my review, and never commit or push.

## 2. AI proposal

Before writing anything, the AI checked the facts the files would state:

- **Fork point.** Its first audit had used `b66ad98` as the fork point. It
  found that the original team kept committing until `5d635c1` (October 29),
  which is the head of their `main`, and corrected the fork point and every
  number based on it.
- **Tests.** Counted at the fork point and now: backend 128 to 484 (test
  methods), frontend 52 to 164 (from running Vitest at both commits). It
  checked that every inherited test file still exists, and found that five
  inherited course-suggestion tests were removed in `c192341` (PR #15) when
  suggestions moved to the catalog, with 13 replacement tests.
- **Inherited M0.** None existed at the fork point; the original team's own
  audit lists it as missing.
- **Badges.** It checked what each badge would show for our fork on `dev` and
  `main`.
- **License.** Neither repository has a license file. The original team's
  Zenodo record licenses their v1.0.0 release (October 21) as CC BY 4.0, and
  13 of their commits after v1.0.0 came before the fork with no license.
- **Libraries.** Versions and licenses were read from each installed package's
  metadata, including the extras psycopg and python-socketio pull in.
- **Startup.** It confirmed that copying `.env.example` unchanged stops the
  backend from starting, by running both cases.

Mistakes the AI made and corrected:

- The original fork point and test counts (above).
- The relabelled DOI badge first rendered as a 404 because parentheses in the
  URL broke the Markdown link; it encoded them.
- A README sentence said all four M0 instruments read the database; only two
  do.
- INSTALL.md said only a topic search downloads the model; saving a profile
  with topics does too.
- THIRD_PARTY_LIBRARIES.md suggested `pip show` for checking licenses, which
  shows a blank license for packages such as psycopg and Flask. It replaced
  this with a command that prints them.
- It linked the language model's Hugging Face page without being able to
  load it, then removed the link.

## 3. Human review

- I chose MIT for our changes, with the original team credited, over
  CC BY 4.0 for everything or waiting for the team.
- I chose to point the badges at `main`, which tutors mark, even though they
  show no status until `dev` is merged.
- I chose to keep the DOI badge, relabelled as the original project's.
- I reviewed each task before the next one started, and committed each myself.
- The source of the course catalog CSV is unknown to me, so it is marked to be
  confirmed by Savanah, who added it.

## 4. Final version

- **README badges**: Build, Tests and Quality, Coverage, Code Style, Formatter
  and Syntax now track `moeyk210/PackConnect` on `main`; the DOI badge reads
  "Original project (Project 2) DOI".
- **README "Project 3: what we changed"**: the fork point and original team,
  what we inherited, a table of the four milestones (issue, PR, lead, what is
  new), supporting work, test counts before and after, how inherited tests
  changed, and the M0 claims with their instruments and results, labelled as
  demo, simulated or hand-written data.
- **`INSTALL.md`**: requirements, backend and frontend setup, a choice between
  the team's Supabase project and a local seeded database, tests, updating
  after a pull, and benchmark tools.
- **`LICENSE.md`**: MIT for changes after `5d635c1`, the original team's
  v1.0.0 credited under CC BY 4.0, and their later commits credited with no
  license claimed.
- **`THIRD_PARTY_LIBRARIES.md`**: every direct dependency and extra with its
  required range, checked version and license, plus the language model, the
  course catalog data, PostgreSQL, pgvector and Supabase.

## 5. Verification

- [x] Tests pass: no code changed on this branch. CI passed on `dev` before it
      was branched.
- [x] Ran it manually: each task was reviewed before it was committed.

Other checks:

- Every badge, issue, pull request and documentation link resolves, and every
  README anchor used exists.
- The MIT text matches GitHub's canonical MIT license exactly.
- The backend starts with a blank `SUPABASE_URL` and refuses the example's
  placeholder, as INSTALL.md describes.
- The license command in THIRD_PARTY_LIBRARIES.md prints `LGPL-3.0-only` for
  psycopg and `BSD-3-Clause` for Flask.
