import { GRADES, normalizeGradeKey } from '../utils/grading'

/**
 * Small pill badge: ELITE / ABOVE AVG / AVG / BELOW AVG / POOR
 *
 * JetBrains Mono, 8-9px, font-weight 600.
 * Color + background from grading table.
 *
 * @param {object} props
 * @param {string} props.grade - Grade key or label string
 * @param {string} [props.size] - "sm" (default) or "md"
 */
export default function GradeBadge({ grade, size = 'sm' }) {
  const key = normalizeGradeKey(grade)
  const info = GRADES[key] || GRADES.AVG

  const sizeClasses = size === 'md'
    ? 'px-2.5 py-1 text-[10px]'
    : 'px-1.5 py-0.5 text-[8px]'

  return (
    <span
      className={`inline-flex items-center rounded-full font-semibold tracking-wide whitespace-nowrap ${sizeClasses}`}
      style={{
        fontFamily: "'JetBrains Mono', monospace",
        color: info.color,
        backgroundColor: info.bg,
      }}
    >
      {info.label}
    </span>
  )
}
