import { useState } from 'react'
import { useAnalysis } from '../hooks/useAnalysis'
import { Sidebar } from './Sidebar'
import { ProgressStream } from './ProgressStream'
import { RankingTable } from './RankingTable'
import { MetricsCards } from './MetricsCards'
import { AssetAnalysis } from './AssetAnalysis'
import { ComparisonChart } from './ComparisonChart'
import { AgentChat } from './AgentChat'
import { PortfolioSection } from './PortfolioSection'
import { OptionsLab } from './OptionsLab'
import { ExportButtons } from './ExportButtons'
import { AlertCircle } from 'lucide-react'

export function Dashboard() {
  const {
    submitAnalysis,
    jobId,
    progress,
    result,
    error,
    loading,
    reset,
  } = useAnalysis()

  const [tickers, setTickers] = useState(
    localStorage.getItem('equitymind_tickers')?.split(',') || ['SBER', 'GAZP']
  )
  const [period, setPeriod] = useState(
    localStorage.getItem('equitymind_period') || '1y'
  )
  const [source, setSource] = useState(
    localStorage.getItem('equitymind_source') || 'moex'
  )
  const [selectedAsset, setSelectedAsset] = useState(null)

  const handleTickersChange = (newTickers) => {
    setTickers(newTickers)
    localStorage.setItem('equitymind_tickers', newTickers.join(','))
  }

  const handlePeriodChange = (newPeriod) => {
    setPeriod(newPeriod)
    localStorage.setItem('equitymind_period', newPeriod)
  }

  const handleSourceChange = (newSource) => {
    setSource(newSource)
    localStorage.setItem('equitymind_source', newSource)
  }

  const handleAnalyze = async () => {
    if (tickers.length === 0) return
    setSelectedAsset(null)
    await submitAnalysis({
      tickers,
      period,
      interval: '1d',
      return_basis: 'cumulative',
      with_ai: true,
      with_backtest: true,
      source,
    })
  }

  return (
    <div className="flex h-screen bg-[#F4F7F4]">
      {/* Боковая панель */}
      <Sidebar
        tickers={tickers}
        onTickersChange={handleTickersChange}
        onAnalyze={handleAnalyze}
        disabled={loading}
        period={period}
        onPeriodChange={handlePeriodChange}
        source={source}
        onSourceChange={handleSourceChange}
      />

      {/* Основной контент */}
      <div className="flex-1 overflow-auto">
        <div className="p-8">
          <div className="max-w-7xl mx-auto">
            {/* Шапка */}
            <div className="mb-8">
              <h1 className="text-4xl font-bold mb-2">
                Аналитика рынков{' '}
                <span className="bg-gradient-to-r from-sber-500 to-teal-500 bg-clip-text text-transparent">
                  EquityMind
                </span>
              </h1>
              <p className="text-gray-600">
                Количественная аналитика с AI-комментариями — без советов и прогнозов
              </p>
            </div>

            {/* Ошибка */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6 flex gap-3">
                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-semibold text-red-900">Ошибка</h3>
                  <p className="text-red-700 text-sm mt-1">{error}</p>
                  <button
                    onClick={reset}
                    className="text-sm text-red-600 hover:text-red-700 font-medium mt-2"
                  >
                    Попробовать снова
                  </button>
                </div>
              </div>
            )}

            {/* Прогресс */}
            {loading && progress && <ProgressStream progress={progress} />}

            {/* Результаты */}
            {result && !loading && (
              <>
                {/* Оповещения */}
                {result.alerts && result.alerts.length > 0 && (
                  <div className="mb-8 space-y-3">
                    {result.alerts.map((alert, idx) => (
                      <div
                        key={idx}
                        className={`p-4 rounded-xl border ${
                          alert.severity === 'critical'
                            ? 'bg-red-50 border-red-200'
                            : 'bg-amber-50 border-amber-200'
                        }`}
                      >
                        <p
                          className={`text-sm font-medium ${
                            alert.severity === 'critical'
                              ? 'text-red-900'
                              : 'text-amber-900'
                          }`}
                        >
                          ⚠️ {alert.message}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Экспорт */}
                <div className="mb-6 flex justify-end">
                  <ExportButtons jobId={jobId} />
                </div>

                {/* Карточки метрик */}
                <div className="mb-8">
                  <h2 className="text-2xl font-bold mb-4">Обзор портфеля</h2>
                  <MetricsCards assets={result.assets} />
                </div>

                {/* Сравнение динамики (при 2+ активах) */}
                <div className="mb-8">
                  <ComparisonChart
                    assets={result.assets}
                    benchmark={result.benchmark}
                  />
                </div>

                {/* Рейтинг */}
                <div className="mb-8">
                  <RankingTable
                    comparison={result.comparison}
                    onSelectAsset={setSelectedAsset}
                  />
                </div>

                {/* Портфельная аналитика: граница, корреляции, аллокации */}
                {result.portfolio && (
                  <div className="mb-8">
                    <PortfolioSection
                      portfolio={result.portfolio}
                      assets={result.assets}
                    />
                  </div>
                )}

                {/* AI-агент */}
                {jobId && (
                  <div className="mb-8">
                    <AgentChat jobId={jobId} />
                  </div>
                )}

                {/* Не загрузилось */}
                {result.failures && Object.keys(result.failures).length > 0 && (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-8">
                    <p className="text-sm text-amber-900 font-medium">
                      Не удалось загрузить: {Object.keys(result.failures).join(', ')}.
                      Подсказка: тикеры Мосбиржи (SBER, GAZP…) требуют источник «Мосбиржа»,
                      а AAPL/BTC-USD — «Yahoo».
                    </p>
                  </div>
                )}

                {/* Детальный анализ */}
                {selectedAsset && result.assets[selectedAsset] && (
                  <div className="mb-8">
                    <button
                      onClick={() => setSelectedAsset(null)}
                      className="text-sm text-gray-500 hover:text-gray-700 mb-4"
                    >
                      ← Назад к рейтингу
                    </button>
                    <AssetAnalysis
                      ticker={selectedAsset}
                      asset={result.assets[selectedAsset]}
                      onClose={() => setSelectedAsset(null)}
                    />
                  </div>
                )}

                {/* Дисклеймер */}
                <p className="text-xs text-gray-400 border-t border-gray-200 pt-4 mt-4">
                  Учебная аналитика рынков — не является индивидуальной инвестиционной
                  рекомендацией. Все показатели описывают прошлое и не предсказывают
                  будущую доходность.
                </p>
              </>
            )}

            {/* Пустое состояние */}
            {!loading && !result && !error && (
              <div className="text-center py-16">
                <div className="inline-block p-8 bg-white rounded-xl border border-gray-200 shadow-sm">
                  <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-gradient-to-br from-sber-500 to-teal-400" />
                  <h3 className="text-2xl font-semibold text-gray-900 mb-2">
                    Готов к анализу
                  </h3>
                  <p className="text-gray-600 mb-6">
                    Выбери инструменты в боковой панели и нажми «Запустить анализ»
                  </p>
                  <p className="text-sm text-gray-500">
                    Анализ занимает 30–120 секунд в зависимости от числа бумаг
                  </p>
                </div>
              </div>
            )}

            {/* Опционная лаборатория — работает и без анализа */}
            {!loading && (
              <div className="mt-8">
                <OptionsLab />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
