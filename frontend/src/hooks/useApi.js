import { useState, useEffect, useRef, useCallback } from 'react'

// In dev, Vite proxy handles /api → localhost:8000.
// In production, VITE_API_URL points to the deployed backend.
const API_BASE = (import.meta.env.VITE_API_URL || '') + '/api'
const cache = new Map()
const CACHE_TTL = 5 * 60 * 1000 // 5 minutes

/**
 * Generic API fetch hook with caching and loading/error state.
 *
 * @param {string} endpoint - API path relative to /api (e.g. "/benchmarks/current")
 * @param {object} options
 * @param {boolean} options.enabled - Whether to fetch (default true)
 * @param {number} options.cacheTtl - Cache TTL in ms (default 5 min)
 * @param {any[]} options.deps - Additional dependency array for refetching
 */
export function useApi(endpoint, { enabled = true, cacheTtl = CACHE_TTL, deps = [] } = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const abortRef = useRef(null)

  const fetchData = useCallback(async () => {
    if (!endpoint || !enabled) return

    const url = `${API_BASE}${endpoint}`

    // Check cache
    const cached = cache.get(url)
    if (cached && Date.now() - cached.timestamp < cacheTtl) {
      setData(cached.data)
      setLoading(false)
      setError(null)
      return
    }

    // Abort previous request
    if (abortRef.current) {
      abortRef.current.abort()
    }
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)

    try {
      const response = await fetch(url, { signal: controller.signal })
      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`)
      }
      const json = await response.json()
      cache.set(url, { data: json, timestamp: Date.now() })
      setData(json)
      setError(null)
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message)
      }
    } finally {
      setLoading(false)
    }
  }, [endpoint, enabled, cacheTtl, ...deps])

  useEffect(() => {
    fetchData()
    return () => {
      if (abortRef.current) {
        abortRef.current.abort()
      }
    }
  }, [fetchData])

  const refetch = useCallback(() => {
    const url = `${API_BASE}${endpoint}`
    cache.delete(url)
    return fetchData()
  }, [endpoint, fetchData])

  return { data, loading, error, refetch }
}

/**
 * Direct fetch utility (non-hook) for one-off API calls.
 */
export async function apiFetch(endpoint) {
  const url = `${API_BASE}${endpoint}`
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

/** Clear the entire API cache. */
export function clearApiCache() {
  cache.clear()
}
