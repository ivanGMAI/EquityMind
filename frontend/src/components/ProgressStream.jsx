export function ProgressStream({ progress }) {
  if (!progress) return null

  const percent = Math.round(progress.progress * 100)
  const steps = [
    { name: 'Данные', percent: 25 },
    { name: 'Метрики', percent: 50 },
    { name: 'AI-анализ', percent: 75 },
    { name: 'Готово', percent: 100 },
  ]

  return (
    <div className="bg-gradient-to-r from-sber-50 to-teal-50 rounded-xl p-8 mb-8 border border-sber-200">
      <h3 className="text-lg font-semibold mb-6">Анализирую…</h3>

      {/* Прогресс-бар */}
      <div className="mb-6">
        <div className="flex justify-between items-center mb-3">
          <span className="text-sm font-medium text-gray-700">
            {progress.current_step}
          </span>
          <span className="text-sm font-semibold text-sber-600 num">{percent}%</span>
        </div>
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      {/* Индикаторы шагов */}
      <div className="grid grid-cols-4 gap-2">
        {steps.map((step, idx) => {
          const isActive = percent >= step.percent
          return (
            <div key={idx} className="text-center">
              <div
                className={`h-10 rounded-xl flex items-center justify-center font-medium text-sm transition-all ${
                  isActive
                    ? 'bg-sber-500 text-white'
                    : 'bg-white border border-gray-300 text-gray-700'
                }`}
              >
                {isActive ? '✓' : step.percent + '%'}
              </div>
              <p className="text-xs text-gray-600 mt-2">{step.name}</p>
            </div>
          )
        })}
      </div>

      {/* Статус */}
      <p className="text-sm text-gray-600 mt-6 text-center">
        {progress.status === 'running' && 'Обрабатываю данные — это займёт меньше минуты…'}
        {progress.status === 'queued' && 'В очереди на обработку…'}
        {progress.status === 'done' && 'Готово!'}
      </p>
    </div>
  )
}
