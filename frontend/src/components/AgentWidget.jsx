import { useState } from 'react'
import { Bot, X } from 'lucide-react'
import { AgentChat } from './AgentChat'

// Плавающий AI-аналитик: кружок в правом нижнем углу с подписью. По клику
// открывается панель чата. Работает поверх любого состояния страницы.
export function AgentWidget({ jobId }) {
  const [open, setOpen] = useState(false)

  return (
    <>
      {/* Панель чата */}
      {open && (
        <div className="fixed bottom-24 right-4 sm:right-6 z-50 w-[min(420px,94vw)] max-h-[72vh] bg-white dark:bg-night-card rounded-2xl shadow-2xl border border-gray-200 dark:border-night-border flex flex-col overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-sber-500 to-teal-400 text-white shrink-0">
            <div className="flex items-center gap-2 font-semibold">
              <Bot size={18} /> AI-аналитик
            </div>
            <button
              onClick={() => setOpen(false)}
              aria-label="Закрыть"
              className="hover:opacity-80 transition-opacity"
            >
              <X size={18} />
            </button>
          </div>
          <div className="p-4 overflow-y-auto">
            {jobId ? (
              <AgentChat jobId={jobId} embedded />
            ) : (
              <p className="text-sm text-gray-600 dark:text-night-sub">
                Запусти анализ бумаг слева — и я отвечу на вопросы о них на основе
                реальных цифр (метрики, рейтинг, портфель, оценка опционов).
              </p>
            )}
          </div>
        </div>
      )}

      {/* Кнопка-кружок с подписью */}
      <div className="fixed bottom-6 right-4 sm:right-6 z-50 flex items-center gap-3">
        {!open && (
          <span className="hidden sm:inline-block bg-white dark:bg-night-card text-gray-700 dark:text-night-sub text-sm font-medium px-3 py-1.5 rounded-full shadow-md border border-gray-200 dark:border-night-border">
            Спросить AI-аналитика
          </span>
        )}
        <button
          onClick={() => setOpen((o) => !o)}
          title="AI-аналитик — спросить о бумагах"
          aria-label="AI-аналитик"
          className="relative w-14 h-14 rounded-full bg-gradient-to-br from-sber-500 to-teal-400 text-white shadow-lg flex items-center justify-center hover:scale-105 active:scale-95 transition-transform"
        >
          {open ? <X size={24} /> : <Bot size={26} />}
          {!open && (
            <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 bg-teal-300 rounded-full border-2 border-white dark:border-night-card animate-pulse" />
          )}
        </button>
      </div>
    </>
  )
}
