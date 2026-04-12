/**
 * Grading system — maps percentile ranks to grades, colors, and backgrounds.
 *
 * Grade thresholds (from CLAUDE.md):
 *   Elite      >= 90th   #34D399
 *   Above Avg  >= 75th   #6EE7B7
 *   Average    25th-75th #8892A8
 *   Below Avg  <= 25th   #FBBF24
 *   Poor       <= 10th   #F87171
 *
 * For stats where lower is better (ERA, BB%, Hard Hit%, Barrel%),
 * the percentile should already be inverted before calling these functions.
 */

export const GRADES = {
  ELITE: {
    label: 'ELITE',
    color: '#34D399',
    bg: 'rgba(52,211,153, 0.20)',
  },
  ABOVE_AVG: {
    label: 'ABOVE AVG',
    color: '#6EE7B7',
    bg: 'rgba(110,231,183, 0.12)',
  },
  AVG: {
    label: 'AVG',
    color: '#8892A8',
    bg: 'rgba(255,255,255, 0.08)',
  },
  BELOW_AVG: {
    label: 'BELOW AVG',
    color: '#FBBF24',
    bg: 'rgba(251,191,36, 0.15)',
  },
  POOR: {
    label: 'POOR',
    color: '#F87171',
    bg: 'rgba(248,113,113, 0.15)',
  },
}

/** All grades in order from best to worst, for legend display. */
export const GRADE_ORDER = ['ELITE', 'ABOVE_AVG', 'AVG', 'BELOW_AVG', 'POOR']

/**
 * Convert a percentile (1-99) to a grade key.
 * For lower-is-better stats, pass the already-inverted percentile.
 */
export function percentileToGrade(percentile) {
  if (percentile == null) return 'AVG'
  if (percentile >= 90) return 'ELITE'
  if (percentile >= 75) return 'ABOVE_AVG'
  if (percentile > 25) return 'AVG'
  if (percentile > 10) return 'BELOW_AVG'
  return 'POOR'
}

/**
 * Get the full grade object { label, color, bg } for a grade key.
 */
export function getGradeInfo(gradeKey) {
  return GRADES[gradeKey] || GRADES.AVG
}

/**
 * Get grade info directly from a percentile.
 */
export function gradeFromPercentile(percentile) {
  return getGradeInfo(percentileToGrade(percentile))
}

/**
 * Map a grade string from the API (e.g. "ELITE", "ABOVE AVG") to our grade key.
 */
export function normalizeGradeKey(gradeStr) {
  if (!gradeStr) return 'AVG'
  const upper = gradeStr.toUpperCase().trim()
  if (upper === 'ELITE') return 'ELITE'
  if (upper === 'ABOVE AVG' || upper === 'ABOVE_AVG') return 'ABOVE_AVG'
  if (upper === 'AVG' || upper === 'AVERAGE') return 'AVG'
  if (upper === 'BELOW AVG' || upper === 'BELOW_AVG') return 'BELOW_AVG'
  if (upper === 'POOR') return 'POOR'
  return 'AVG'
}

/** Stats where lower values are better. */
export const LOWER_IS_BETTER = new Set([
  'era', 'fip', 'xfip', 'xera',
  'bb_pct', 'hard_hit_pct', 'barrel_pct',
  'o_swing_pct', 'chase_rate',
  'hard_hit_pct_against', 'barrel_pct_against',
])

/**
 * Invert a percentile for lower-is-better stats.
 * If the stat is lower-is-better, a raw percentile of 90
 * (meaning the value is high) should display as 10 (bad).
 */
export function adjustPercentile(percentile, statName) {
  if (LOWER_IS_BETTER.has(statName)) {
    return 100 - percentile
  }
  return percentile
}
