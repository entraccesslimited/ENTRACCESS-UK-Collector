import { useCallback, useEffect, useState } from 'react'

import { api } from './api'

/** Load a GET endpoint, with a reload function for after a change. */
export function useLoad<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(path !== null)

  const reload = useCallback(async () => {
    if (path === null) return
    setLoading(true)
    try {
      setData(await api<T>(path))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load this.')
    } finally {
      setLoading(false)
    }
  }, [path])

  useEffect(() => {
    void reload()
  }, [reload])

  return { data, error, loading, reload }
}
