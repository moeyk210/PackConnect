import { useEffect, useState } from 'react'
import ReputationBadges from './ReputationBadges'
import './CoursePage.css'

const RATING_SCALE = 5

const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`

function CourseRating({ label, rating }) {
  return (
    <div className="course-rating">
      <dt>{label}</dt>
      {rating ? (
        <dd>
          <strong>{rating.average.toFixed(1)}</strong> / {RATING_SCALE}
          <span> · {plural(rating.count, 'student')}</span>
        </dd>
      ) : (
        <dd className="course-rating-empty">Not enough ratings yet</dd>
      )}
    </div>
  )
}

export default function CoursePage({ code }) {
  const [result, setResult] = useState({ code: '', status: '', data: null })
  const status = result.code === code ? result.status : 'loading'

  useEffect(() => {
    const controller = new AbortController()
    const finish = (next) => {
      if (!controller.signal.aborted) setResult({ code, ...next })
    }
    async function load() {
      try {
        const response = await fetch(
          `/api/courses/${encodeURIComponent(code)}`,
          { signal: controller.signal },
        )
        if (response.status === 404) return finish({ status: 'missing' })
        if (!response.ok) throw new Error('Could not load this course.')
        const data = await response.json()
        if (!data?.course || !Array.isArray(data.advisors) || !data.ratings) {
          throw new Error('Invalid course data.')
        }
        finish({ status: 'ready', data })
      } catch {
        finish({ status: 'error' })
      }
    }
    load()
    return () => controller.abort()
  }, [code])

  if (status === 'loading') {
    return (
      <p className="empty-state" role="status">
        Loading course...
      </p>
    )
  }
  if (status === 'missing') {
    return (
      <div className="empty-state">
        <h2>Course not found</h2>
        <p>{code} is not in the course catalog.</p>
        <a href="#/app">Back to Find peers</a>
      </div>
    )
  }
  if (status === 'error') {
    return (
      <p className="error-message" role="alert">
        Could not load this course. Please try again.
      </p>
    )
  }

  const { course, advisors, ratings } = result.data
  const hasRatings = ratings.workload || ratings.difficulty
  return (
    <section
      className="profile-panel course-page"
      aria-labelledby="course-title"
    >
      <a className="profile-back" href="#/app">
        Back to Find peers
      </a>
      <h2 id="course-title">
        <span className="course-page-code">{course.code}</span> {course.title}
      </h2>
      {course.description ? (
        <p className="profile-bio">{course.description}</p>
      ) : (
        <p className="profile-note">No description has been added yet.</p>
      )}

      <h3>Workload and difficulty</h3>
      {hasRatings ? (
        <dl className="course-ratings">
          <CourseRating label="Workload" rating={ratings.workload} />
          <CourseRating label="Difficulty" rating={ratings.difficulty} />
        </dl>
      ) : (
        <p className="profile-note">
          Averages appear once at least {ratings.min_ratings} students who took
          this course have rated it.
        </p>
      )}

      <h3>Available advisors</h3>
      {advisors.length === 0 ? (
        <p className="empty-state">
          No available advisors have completed this course yet.
        </p>
      ) : (
        <>
          <p className="profile-note">Best rated first.</p>
          <ol className="course-advisors" aria-label="Available advisors">
            {advisors.map((advisor, index) => (
              <li key={advisor.id} className="course-advisor">
                <span className="course-advisor-rank" aria-hidden="true">
                  {index + 1}
                </span>
                <div>
                  <a href={`#/app/students/${advisor.id}`}>{advisor.name}</a>
                  <p className="student-program">
                    {[advisor.program, advisor.year]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                  <ReputationBadges reputation={advisor.reputation} />
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  )
}
