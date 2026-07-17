import { useState, useCallback, useRef } from 'react'
import { analyzeApi } from '../api/client'

export function useAnalysis() {
  const [jobId, setJobId] = useState(null)
  const [progress, setProgress] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const pollIntervalRef = useRef(null)

  const submitAnalysis = useCallback(async (params) => {
    setLoading(true)
    setError(null)
    setJobId(null)
    setProgress(null)
    setResult(null)

    try {
      const response = await analyzeApi.submit(params)
      const data = response.data
      setJobId(data.job_id)

      // Start polling immediately
      await pollProgress(data.job_id)
    } catch (err) {
      const message =
        err.response?.data?.detail ||
        err.message ||
        'Failed to submit analysis'
      setError(message)
      setLoading(false)
    }
  }, [])

  const pollProgress = useCallback(async (id) => {
    // Clear any existing interval
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
    }

    // Poll every second
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
  }, [])

  const fetchResult = useCallback(async (id) => {
    try {
      const response = await analyzeApi.getResult(id)
      const data = response.data
      setResult(data)
    } catch (err) {
      const message = err.response?.data?.detail || 'Failed to fetch result'
      setError(message)
    }
  }, [])

  const reset = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
    }
    setJobId(null)
    setProgress(null)
    setResult(null)
    setError(null)
    setLoading(false)
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
