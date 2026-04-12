/**
 * Stat formatting utilities — delta display, +/- prefix, ordinal suffixes,
 * number formatting for different stat types.
 */

/**
 * Format a stat value for display based on the stat type.
 *
 * - ERA/FIP/xFIP/xERA: 2 decimal places (e.g. "3.42")
 * - Percentages (K%, BB%, etc.): 1 decimal + "%" (e.g. "28.4%")
 * - Rates (wOBA, xBA, BABIP, etc.): 3 decimal places (e.g. ".321")
 * - wRC+: integer (e.g. "118")
 * - Velocity: 1 decimal + " mph" (e.g. "95.2 mph")
 * - Run-based (BsR, OAA, DRS): 1 decimal (e.g. "+2.3")
 * - Default: 2 decimal places
 */
export function formatStat(value, statName) {
  if (value == null || value === '' || Number.isNaN(value)) return '—'

  const v = Number(value)
  const name = (statName || '').toLowerCase()

  // ERA family
  if (['era', 'fip', 'xfip', 'xera', 'whip'].includes(name)) {
    return v.toFixed(2)
  }

  // Percentage stats
  if (name.endsWith('_pct') || name.endsWith('pct') || name.includes('pct')) {
    return `${v.toFixed(1)}%`
  }

  // Rate stats (.xxx format)
  if (['woba', 'xba', 'xslg', 'xwoba', 'babip', 'avg', 'obp', 'slg'].includes(name)) {
    return v.toFixed(3).replace(/^0/, '')
  }

  // Integer stats
  if (['wrc_plus', 'games', 'pa', 'ab', 'runs_scored', 'runs_allowed'].includes(name)) {
    return Math.round(v).toString()
  }

  // Velocity
  if (['avg_velo', 'release_speed', 'sprint_speed'].includes(name)) {
    return `${v.toFixed(1)}`
  }

  // Run-value stats (show sign)
  if (['bsr', 'oaa', 'drs', 'framing_runs', 'run_diff'].includes(name)) {
    return formatDelta(v, 1)
  }

  return v.toFixed(2)
}

/**
 * Format a delta value with explicit +/- prefix.
 * @param {number} value - The delta value
 * @param {number} decimals - Decimal places (default 2)
 */
export function formatDelta(value, decimals = 2) {
  if (value == null || Number.isNaN(value)) return '—'
  const v = Number(value)
  const prefix = v > 0 ? '+' : ''
  return `${prefix}${v.toFixed(decimals)}`
}

/**
 * Format a delta with "above avg" / "below avg" suffix.
 */
export function formatDeltaWithContext(value, lowerIsBetter = false) {
  if (value == null || Number.isNaN(value)) return '—'
  const v = Number(value)
  const abs = Math.abs(v).toFixed(2)

  if (Math.abs(v) < 0.005) return 'At league average'

  // For lower-is-better stats, negative delta = good (below average = good)
  if (lowerIsBetter) {
    return v < 0 ? `${abs} below avg` : `${abs} above avg`
  }
  return v > 0 ? `${abs} above avg` : `${abs} below avg`
}

/**
 * Add ordinal suffix to a number: 1st, 2nd, 3rd, 4th, etc.
 */
export function ordinal(n) {
  if (n == null) return '—'
  const num = Math.round(n)
  const suffixes = ['th', 'st', 'nd', 'rd']
  const mod100 = num % 100
  const suffix = suffixes[(mod100 - 20) % 10] || suffixes[mod100] || suffixes[0]
  return `${num}${suffix}`
}

/**
 * Format percentile for display: "72nd percentile"
 */
export function formatPercentile(percentile) {
  if (percentile == null) return '—'
  return `${ordinal(percentile)} percentile`
}

/**
 * Format a win-loss record: "45-32"
 */
export function formatRecord(wins, losses) {
  if (wins == null || losses == null) return '—'
  return `${wins}-${losses}`
}

/**
 * Plain English stat labels for display.
 */
export const STAT_LABELS = {
  // Pitching
  era: 'ERA',
  fip: 'FIP',
  xfip: 'xFIP',
  xera: 'xERA',
  k_pct: 'K%',
  bb_pct: 'BB%',
  k_bb_pct: 'K-BB%',
  swstr_pct: 'SwStr%',
  csw_pct: 'CSW%',
  hard_hit_pct: 'Hard Hit%',
  barrel_pct: 'Barrel%',
  avg_velo: 'Velocity',
  whiff_pct: 'Whiff%',
  // Hitting
  wrc_plus: 'wRC+',
  woba: 'wOBA',
  xba: 'xBA',
  xslg: 'xSLG',
  xwoba: 'xwOBA',
  avg_exit_velo: 'Avg Exit Velo',
  o_swing_pct: 'O-Swing%',
  z_contact_pct: 'Z-Contact%',
  chase_rate: 'Chase Rate',
  sprint_speed: 'Sprint Speed',
  bsr: 'BsR',
  babip: 'BABIP',
  avg: 'AVG',
  obp: 'OBP',
  slg: 'SLG',
  // Defense
  oaa: 'OAA',
  drs: 'DRS',
  framing_runs: 'Framing Runs',
  // Team
  team_era: 'Team ERA',
  team_fip: 'Team FIP',
  team_wrc_plus: 'Team wRC+',
  team_woba: 'Team wOBA',
  run_diff: 'Run Diff',
  pythag_wins: 'Pythag W',
}

/**
 * Plain English explanations for stats.
 */
export const STAT_EXPLANATIONS = {
  era: 'Runs allowed per 9 innings',
  fip: 'Pitching quality removing luck and defense',
  xfip: 'FIP normalizing home run luck',
  xera: 'Expected ERA from batted ball quality',
  k_pct: 'How often he strikes batters out',
  bb_pct: 'How often he gives free bases',
  k_bb_pct: 'Strikeouts minus walks — best quick measure',
  swstr_pct: 'How often batters swing and miss',
  csw_pct: 'Called strikes + whiffs — stuff quality score',
  hard_hit_pct: '% of batted balls hit 95+ mph',
  barrel_pct: '% of perfect-contact damage balls',
  avg_velo: 'Fastball speed',
  whiff_pct: 'Swing-and-miss rate',
  wrc_plus: 'Overall hitting value (100 = exactly average)',
  woba: 'Weighted on-base — values each outcome by run value',
  xba: 'Expected batting avg from contact quality',
  xslg: 'Expected slugging from contact quality',
  xwoba: 'Expected wOBA from exit velo + launch angle',
  avg_exit_velo: 'How hard he hits the ball on average',
  o_swing_pct: 'How often he chases bad pitches',
  z_contact_pct: 'How often he makes contact on strikes',
  chase_rate: 'How often he swings at bad pitches',
  sprint_speed: 'Running speed (ft/sec)',
  bsr: 'Baserunning value in runs',
  babip: 'Batting avg on balls in play — luck indicator',
  oaa: 'Outs Above Average — fielding value (0 = avg)',
  drs: 'Defensive Runs Saved vs average fielder',
  framing_runs: 'Extra strikes catcher steals from umpire',
  team_era: 'Team runs allowed per 9 innings',
  team_fip: 'Team pitching quality (defense-independent)',
  team_wrc_plus: 'Team hitting value (100 = average)',
  run_diff: 'Runs scored minus runs allowed',
}
