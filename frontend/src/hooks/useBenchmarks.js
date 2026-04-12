import { useMemo } from 'react'
import { useApi } from './useApi'
import { percentileToGrade, getGradeInfo, LOWER_IS_BETTER } from '../utils/grading'

/**
 * Hook to fetch and cache current MLB benchmarks.
 * Returns benchmarks indexed by stat_name + position_group for fast lookup.
 */
export function useBenchmarks() {
  const { data, loading, error, refetch } = useApi('/benchmarks/current', {
    cacheTtl: 10 * 60 * 1000, // 10 minutes — benchmarks update weekly
  })

  const benchmarkMap = useMemo(() => {
    if (!data) return {}
    const map = {}
    for (const b of data) {
      const key = `${b.stat_name}__${b.position_group}`
      map[key] = b
    }
    return map
  }, [data])

  /**
   * Look up benchmark data for a specific stat + position group.
   */
  function getBenchmark(statName, positionGroup = 'ALL_HITTERS') {
    return benchmarkMap[`${statName}__${positionGroup}`] || null
  }

  /**
   * Get MLB average for a stat.
   */
  function getMlbAvg(statName, positionGroup = 'ALL_HITTERS') {
    const b = getBenchmark(statName, positionGroup)
    return b ? b.mean : null
  }

  return {
    benchmarks: data || [],
    benchmarkMap,
    getBenchmark,
    getMlbAvg,
    loading,
    error,
    refetch,
  }
}

/**
 * Hook to fetch all benchmarked stats for a specific player.
 * Returns an object keyed by stat_name for fast lookup.
 */
export function usePlayerBenchmarks(playerId) {
  const { data, loading, error, refetch } = useApi(
    playerId ? `/benchmarks/player/${playerId}` : null,
    { enabled: !!playerId }
  )

  const statMap = useMemo(() => {
    if (!data) return {}
    const map = {}
    for (const pb of data) {
      map[pb.stat_name] = pb
    }
    return map
  }, [data])

  /**
   * Get a player's benchmarked stat with grade info.
   */
  function getPlayerStat(statName) {
    const pb = statMap[statName]
    if (!pb) return null
    const gradeKey = percentileToGrade(pb.percentile)
    return {
      ...pb,
      gradeKey,
      ...getGradeInfo(gradeKey),
    }
  }

  return {
    playerBenchmarks: data || [],
    statMap,
    getPlayerStat,
    loading,
    error,
    refetch,
  }
}

/**
 * Hook to fetch pitch-type benchmarks for a specific pitch type.
 */
export function usePitchTypeBenchmarks(pitchType) {
  const { data, loading, error } = useApi(
    pitchType ? `/benchmarks/pitch-type/${pitchType}` : null,
    { enabled: !!pitchType }
  )

  const statMap = useMemo(() => {
    if (!data) return {}
    const map = {}
    for (const b of data) {
      map[b.stat_name] = b
    }
    return map
  }, [data])

  return {
    pitchTypeBenchmarks: data || [],
    statMap,
    loading,
    error,
  }
}
