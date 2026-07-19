import { createContext, useContext, useEffect } from 'react'

const ThemeContext = createContext({ dark: false, toggle: () => {} })

export function ThemeProvider({ children }) {
  // Тёмная тема отключена — приложение всегда светлое.
  useEffect(() => {
    document.documentElement.classList.remove('dark')
    localStorage.removeItem('equitymind_theme')
  }, [])

  return (
    <ThemeContext.Provider value={{ dark: false, toggle: () => {} }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => useContext(ThemeContext)

/** Цвета осей/сеток/подписей Recharts под текущую тему.
 *  Категориальная палитра проверена валидатором на обеих поверхностях
 *  (в тёмной циан затемнён до #0891B2 — иначе выпадает из диапазона светлоты). */
export function useChartTheme() {
  const { dark } = useTheme()
  return dark
    ? {
        grid: '#1F3A2A',
        tick: '#8FA69A',
        axisLine: '#1F3A2A',
        cursor: '#5C7A6A',
        refLine: '#5C7A6A',
        ink: '#CBD9CF',
        palette: ['#21A038', '#2563EB', '#D97706', '#8B5CF6', '#DB2777', '#0891B2'],
      }
    : {
        grid: '#E5E7EB',
        tick: '#6B7280',
        axisLine: '#E5E7EB',
        cursor: '#9CA3AF',
        refLine: '#9CA3AF',
        ink: '#334155',
        palette: ['#21A038', '#2563EB', '#D97706', '#8B5CF6', '#DB2777', '#06B6D4'],
      }
}

/** Классы всплывающей подсказки графиков (HTML-слой). */
export const TOOLTIP_CLASS =
  'bg-white dark:bg-night-hover border border-gray-200 dark:border-night-border rounded-lg shadow-md px-4 py-3 text-sm'
