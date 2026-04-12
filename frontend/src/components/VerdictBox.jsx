import { gradeFromPercentile, normalizeGradeKey, getGradeInfo } from '../utils/grading'

/**
 * Bottom-line plain English summary box.
 *
 * - Blue-tinted background box
 * - Title: "Bottom line — [Name]"
 * - Body: plain English summary referencing key benchmarks
 *
 * @param {object} props
 * @param {string} props.playerName - Player name
 * @param {string} props.verdictText - Plain English verdict body
 * @param {string} [props.verdictGrade] - Grade key for accent color
 */
export default function VerdictBox({ playerName, verdictText, verdictGrade }) {
  const gradeInfo = verdictGrade
    ? getGradeInfo(normalizeGradeKey(verdictGrade))
    : { color: '#60A5FA' }

  return (
    <div
      className="rounded-lg p-4 border"
      style={{
        backgroundColor: 'rgba(14, 51, 134, 0.15)',
        borderColor: 'rgba(14, 51, 134, 0.30)',
      }}
    >
      <h4
        className="text-sm font-semibold mb-2"
        style={{ color: gradeInfo.color }}
      >
        Bottom line — {playerName}
      </h4>
      <p className="text-sm text-text-primary leading-relaxed">
        {verdictText}
      </p>
    </div>
  )
}
