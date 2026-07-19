import { useEffect, useState } from 'react'
import { Dashboard } from './components/Dashboard'
import { analyzeApi } from './api/client'

function App() {
  const [apiReady, setApiReady] = useState(false)
  const [apiError, setApiError] = useState(null)

  useEffect(() => {
    // Проверяем доступность API
    const checkApi = async () => {
      try {
        await analyzeApi.health()
        setApiReady(true)
        setApiError(null)
      } catch (err) {
        setApiError(
          'Не удаётся подключиться к серверу API (http://localhost:8000). ' +
          'Убедись, что FastAPI запущен: python run_api_server.py'
        )
        setApiReady(false)
      }
    }

    checkApi()
    // Повторная проверка каждые 30 секунд
    const interval = setInterval(checkApi, 30000)
    return () => clearInterval(interval)
  }, [])

  if (apiError && !apiReady) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-sber-50 to-teal-50 dark:from-night-bg dark:to-[#0E2A1D]">
        <div className="bg-white dark:bg-night-card rounded-xl shadow-lg p-8 max-w-md">
          <h1 className="text-2xl font-bold text-red-600 dark:text-red-400 mb-4">
            Сервер недоступен
          </h1>
          <p className="text-gray-700 dark:text-night-sub mb-4">{apiError}</p>
          <div className="bg-gray-50 dark:bg-night-hover rounded-xl p-4 mb-4 text-sm text-gray-600 dark:text-night-sub">
            <p className="font-mono">python run_api_server.py</p>
          </div>
          <p className="text-sm text-gray-500 dark:text-night-mut">
            Запусти FastAPI-сервер на порту 8000 — страница обновится автоматически.
          </p>
        </div>
      </div>
    )
  }

  return <Dashboard />
}

export default App
