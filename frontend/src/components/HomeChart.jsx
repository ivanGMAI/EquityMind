import { useEffect, useState } from 'react'
import { analyzeApi } from '../api/client'
import { PriceChart } from './PriceChart'

// График индекса Мосбиржи (IMOEX) на главном экране. Таймфрейм задаётся
// селектором периода сверху и меняется без запуска полного анализа.
export function HomeChart({ period }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    analyzeApi
      .getPrices('IMOEX', 'moex', period)
      .then((res) => {
        if (alive) setData(res.data)
      })
      .catch(() => {
        if (alive) setError('Не удалось загрузить индекс Мосбиржи')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [period])

  if (loading) {
    return (
      <div className="card flex items-center justify-center h-96 text-gray-500 dark:text-night-mut">
        Загружаю график индекса Мосбиржи…
      </div>
    )
  }
  if (error || !data?.history?.length) {
    return (
      <div className="card flex items-center justify-center h-40 text-gray-500 dark:text-night-mut">
        {error || 'Нет данных'}
      </div>
    )
  }

  return (
    <PriceChart
      history={data.history}
      ticker="Индекс Мосбиржи (IMOEX)"
      currency={data.currency}
    />
  )
}
