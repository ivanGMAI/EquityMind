import { useRef, useState } from 'react'
import { Send, Wrench } from 'lucide-react'
import { analyzeApi } from '../api/client'

/** Мини-рендер markdown без зависимостей: **жирный**, `код`,
 *  заголовки ###, маркированные и нумерованные списки. */
function renderInline(text, keyPrefix) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={`${keyPrefix}-${i}`}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={`${keyPrefix}-${i}`} className="bg-gray-100 dark:bg-night-border px-1 rounded text-xs">
          {part.slice(1, -1)}
        </code>
      )
    }
    return part
  })
}

function MarkdownLite({ text }) {
  const lines = (text || '').split('\n')
  const blocks = []
  let list = null

  lines.forEach((line) => {
    const bullet = line.match(/^\s*[-*]\s+(.*)/)
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)/)
    if (bullet || numbered) {
      if (!list) {
        list = []
        blocks.push({ type: 'list', items: list })
      }
      list.push((bullet || numbered)[1])
      return
    }
    list = null
    const heading = line.match(/^#{2,4}\s+(.*)/)
    if (heading) {
      blocks.push({ type: 'heading', text: heading[1] })
    } else if (line.trim()) {
      blocks.push({ type: 'p', text: line })
    }
  })

  return (
    <div className="space-y-2 text-sm leading-relaxed">
      {blocks.map((b, i) => {
        if (b.type === 'heading') {
          return (
            <p key={i} className="font-semibold text-gray-900 dark:text-night-text mt-3">
              {renderInline(b.text, i)}
            </p>
          )
        }
        if (b.type === 'list') {
          return (
            <ul key={i} className="list-disc list-inside space-y-1">
              {b.items.map((item, j) => (
                <li key={j}>{renderInline(item, `${i}-${j}`)}</li>
              ))}
            </ul>
          )
        }
        return <p key={i}>{renderInline(b.text, i)}</p>
      })}
    </div>
  )
}

const EXAMPLES = [
  'У какого актива лучший коэффициент Шарпа и почему?',
  'Сравни риски всех бумаг простыми словами',
  'Оцени 3-месячный ATM-колл на лидера рейтинга при воле 25%',
]

export function AgentChat({ jobId, embedded = false }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const listRef = useRef(null)

  const ask = async (question) => {
    const q = question.trim()
    if (!q || pending) return
    setInput('')
    setPending(true)
    setMessages((m) => [...m, { role: 'user', text: q }])

    try {
      const res = await analyzeApi.askAgent(jobId, q)
      const { answer, model, steps } = res.data
      setMessages((m) => [...m, { role: 'agent', text: answer, model, steps }])
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Агент не ответил'
      setMessages((m) => [...m, { role: 'error', text: detail }])
    } finally {
      setPending(false)
      requestAnimationFrame(() => {
        listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
      })
    }
  }

  return (
    <div className={embedded ? '' : 'card'}>
      {!embedded && <h3 className="card-title">🤖 Спроси AI-аналитика</h3>}
      <p className="card-text mb-4">
        Агент сам вызывает аналитические инструменты (метрики, рейтинг, портфель,
        оценка опционов) и отвечает на основе реальных цифр
      </p>

      {/* Примеры вопросов */}
      {messages.length === 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => ask(ex)}
              disabled={pending}
              className="text-xs px-3 py-1.5 rounded-full border border-sber-200 text-sber-700 hover:bg-sber-50 dark:border-sber-800 dark:text-sber-300 dark:hover:bg-night-hover transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      {/* Сообщения */}
      {messages.length > 0 && (
        <div ref={listRef} className="space-y-3 mb-4 max-h-96 overflow-y-auto pr-1">
          {messages.map((m, i) => {
            if (m.role === 'user') {
              return (
                <div key={i} className="flex justify-end">
                  <div className="bg-sber-100 text-sber-900 dark:bg-sber-900 dark:text-sber-100 rounded-2xl rounded-br-md px-4 py-2 text-sm max-w-[85%]">
                    {m.text}
                  </div>
                </div>
              )
            }
            if (m.role === 'error') {
              return (
                <div key={i} className="bg-red-50 border border-red-200 text-red-800 dark:bg-red-950/40 dark:border-red-900 dark:text-red-300 rounded-xl px-4 py-2 text-sm">
                  {m.text}
                </div>
              )
            }
            return (
              <div key={i} className="bg-white border border-gray-200 dark:bg-night-hover dark:border-night-border rounded-2xl rounded-bl-md px-4 py-3 max-w-[95%]">
                <MarkdownLite text={m.text} />
                {m.steps && m.steps.length > 0 && (
                  <details className="mt-3 text-xs text-gray-500 dark:text-night-mut">
                    <summary className="cursor-pointer flex items-center gap-1.5 select-none">
                      <Wrench size={12} />
                      Вызовы инструментов: {m.steps.length}
                    </summary>
                    <ul className="mt-2 space-y-1 font-mono">
                      {m.steps.map((s, j) => (
                        <li key={j}>
                          {s.tool}({JSON.stringify(s.arguments)})
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                {m.model && (
                  <p className="text-[10px] text-gray-400 dark:text-night-mut mt-2">{m.model}</p>
                )}
              </div>
            )
          })}
          {pending && (
            <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-night-mut px-2">
              <span className="inline-block w-2 h-2 rounded-full bg-sber-500 animate-pulse" />
              Агент рассуждает и вызывает инструменты…
            </div>
          )}
        </div>
      )}

      {/* Ввод */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          ask(input)
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={pending}
          placeholder="Например: у какой бумаги лучший Шарп?"
          className="flex-1 px-4 py-2 input-base"
        />
        <button
          type="submit"
          disabled={pending || !input.trim()}
          className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <Send size={16} />
          Спросить
        </button>
      </form>
    </div>
  )
}
