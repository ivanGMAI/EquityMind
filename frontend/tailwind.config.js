/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Фирменная палитра Сбера: зелёный #21A038 + градиент в бирюзу
        sber: {
          50: '#EAF7EE',
          100: '#D2EEDB',
          200: '#A7DDB8',
          300: '#77CB92',
          400: '#46B56A',
          500: '#21A038',
          600: '#1A8A30',
          700: '#147026',
          800: '#0E561E',
          900: '#093D15',
        },
        primary: '#21A038',
        success: '#21A038',
        warning: '#F59E0B',
        critical: '#E64646',
      },
      fontFamily: {
        // SB Sans Text подхватится, если установлен; иначе системный стек
        sans: ['SB Sans Text', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['SB Sans Mono', 'Consolas', 'Courier New', 'monospace'],
      },
    },
  },
  plugins: [],
}
