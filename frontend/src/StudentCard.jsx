import { availabilityLabel, capacityLabel } from './advisorAvailability'
import ReputationBadges from './ReputationBadges'

// Two-letter initials for the avatar circle, for example "Maya Okafor" -> "MO".
function initials(name) {
  return name
    ?.split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
}

// One advisor in the search results: who they are, whether they are taking
// requests, their reputation, and a link to their full profile.
export default function StudentCard({ student }) {
  return (
    <article className="student-card">
      <div className="avatar">{initials(student.name)}</div>

      <h4>{student.name}</h4>

      <p className="student-program">{student.program || 'NC State Student'}</p>

      {student.year && <p className="student-year">{student.year}</p>}

      {student.advice_topics && (
        <p className="student-year">Can help with {student.advice_topics}</p>
      )}

      <span
        className="available-badge"
        data-availability={student.availability_status}
      >
        {availabilityLabel(student)}
      </span>
      <p className="profile-note">{capacityLabel(student)}</p>
      <ReputationBadges reputation={student.reputation} />

      <a
        className="profile-button peer-profile-link"
        href={`#/app/students/${student.id}`}
      >
        View Profile →
      </a>
    </article>
  )
}
