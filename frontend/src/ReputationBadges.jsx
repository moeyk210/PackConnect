import './ReputationBadges.css'

const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`

// Aggregate advisor stats from the API's `reputation` object. Search cards show
// the compact set; profile pages pass `detailed` to add the helpful percentage.
export default function ReputationBadges({ reputation, detailed = false }) {
  if (!reputation) return null
  const {
    average_rating: average,
    rating_count: ratings,
    helpful_percent: helpful,
    students_helped: helped,
    response_rate: responseRate,
  } = reputation
  const badges = [
    ratings > 0
      ? {
          key: 'rating',
          text: `★ ${average.toFixed(1)}/10 · ${plural(ratings, 'rating')}`,
          highlight: true,
        }
      : { key: 'rating', text: 'No ratings yet' },
  ]
  if (detailed && helpful !== null)
    badges.push({ key: 'helpful', text: `${helpful}% found it helpful` })
  if (helped > 0)
    badges.push({ key: 'helped', text: `${plural(helped, 'student')} helped` })
  if (responseRate !== null)
    badges.push({ key: 'response', text: `${responseRate}% response rate` })

  return (
    <ul className="reputation-badges" aria-label="Advisor reputation">
      {badges.map((badge) => (
        <li
          key={badge.key}
          className={
            badge.highlight ? 'reputation-badge rated' : 'reputation-badge'
          }
        >
          {badge.text}
        </li>
      ))}
    </ul>
  )
}
