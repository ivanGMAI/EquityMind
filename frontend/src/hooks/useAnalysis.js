import { useState, useCallback, useRef } from 'react'
import { analyzeApi } from '../api/client'

// Последний завершённый анализ кэшируется в localStorage, чтобы он не пропадал
// при обновлении страницы (иначе результат живёт только в памяти вкладки).
const STORAGE_KEY = 'equitymind_last_analysis'

function loadCached() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function saveCached(jobId, result) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ jobId, result }))
  } catch {
    // Переполнение квоты localStorage — просто не кэшируем, сессия не ломается.
  }
}

function clearCached() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* ignore */
  }
}

export function useAnalysis() {
  const cached = loadCached()
  const [jobId, setJobId] = useState(cached?.jobId ?? null)
  const [progress, setProgress] = useState(null)
  const [result, setResult] = useState(cached?.result ?? null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const pollIntervalRef = useRef(null)

  const fetchResult = useCallback(async (id) => {
    try {
      const response = await analyzeApi.getResult(id)
      const data = response.data
      setResult(data)
      saveCached(id, data) // переживёт обновление страницы
    } catch (err) {
      const message = err.response?.data?.detail || 'Failed to fetch result'
      setError(message)
    }
  }, [])

  const pollProgress = useCallback(
    async (id) => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }

      pollIntervalRef.current = setInterval(async () => {
        try {
          const response = await analyzeApi.getProgress(id)
          const data = response.data
          setProgress(data)

          if (data.status === 'done') {
            clearInterval(pollIntervalRef.current)
            await fetchResult(id)
            setLoading(false)
          } else if (data.status === 'failed') {
            clearInterval(pollIntervalRef.current)
            setError(data.error || 'Analysis failed')
            setLoading(false)
          }
        } catch (err) {
          clearInterval(pollIntervalRef.current)
          const message = err.response?.data?.detail || 'Failed to fetch progress'
          setError(message)
          setLoading(false)
        }
      }, 1000)
    },
    [fetchResult]
  )

  const submitAnalysis = useCallback(
    async (params) => {
      setLoading(true)
      setError(null)
      setJobId(null)
      setProgress(null)
      setResult(null)

      try {
        const response = await analyzeApi.submit(params)
        const data = response.data
        setJobId(data.job_id)
        await pollProgress(data.job_id)
      } catch (err) {
        const message =
          err.response?.data?.detail || err.message || 'Failed to submit analysis'
        setError(message)
        setLoading(false)
      }
    },
    [pollProgress]
  )

  const reset = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
    }
    setJobId(null)
    setProgress(null)
    setResult(null)
    setError(null)
    setLoading(false)
    clearCached()
  }, [])

  return {
    submitAnalysis,
    jobId,
    progress,
    result,
    error,
    loading,
    reset,
  }
}
