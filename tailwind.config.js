/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        /* 科创极简色彩体系 */
        primary: {
          DEFAULT: 'var(--color-primary)',
          hover: 'var(--color-primary-hover)',
          active: 'var(--color-primary-active)',
        },
        secondary: {
          DEFAULT: 'var(--color-secondary)',
          hover: 'var(--color-secondary-hover)',
        },
        /* 灰度中性色 - 5阶 */
        gray: {
          50: 'var(--color-gray-50)',
          100: 'var(--color-gray-100)',
          200: 'var(--color-gray-200)',
          300: 'var(--color-gray-300)',
          400: 'var(--color-gray-400)',
          500: 'var(--color-gray-500)',
          600: 'var(--color-gray-600)',
          700: 'var(--color-gray-700)',
          800: 'var(--color-gray-800)',
          900: 'var(--color-gray-900)',
        },
        /* 状态色 - 柔化低透明度 */
        success: {
          light: 'var(--color-success-light)',
          DEFAULT: 'var(--color-success)',
          dark: 'var(--color-success-dark)',
        },
        warning: {
          light: 'var(--color-warning-light)',
          DEFAULT: 'var(--color-warning)',
          dark: 'var(--color-warning-dark)',
        },
        error: {
          light: 'var(--color-error-light)',
          DEFAULT: 'var(--color-error)',
          dark: 'var(--color-error-dark)',
        },
        info: {
          light: 'var(--color-info-light)',
          DEFAULT: 'var(--color-info)',
          dark: 'var(--color-info-dark)',
        },
        /* 背景色 */
        bg: {
          primary: 'var(--color-bg-primary)',
          secondary: 'var(--color-bg-secondary)',
          tertiary: 'var(--color-bg-tertiary)',
          card: 'var(--color-bg-card)',
          dark: {
            primary: 'var(--color-dark-bg-primary)',
            secondary: 'var(--color-dark-bg-secondary)',
            tertiary: 'var(--color-dark-bg-tertiary)',
            card: 'var(--color-dark-bg-card)',
          }
        },
        /* 文字色 */
        text: {
          primary: 'var(--color-text-primary)',
          secondary: 'var(--color-text-secondary)',
          tertiary: 'var(--color-text-tertiary)',
          inverse: 'var(--color-text-inverse)',
        },
        /* 边框色 */
        border: {
          DEFAULT: 'var(--color-border)',
          light: 'var(--color-border-light)',
          dark: 'var(--color-border-dark)',
        },
        /* 数据可视化色板 */
        viz: {
          1: 'var(--color-viz-1)',
          2: 'var(--color-viz-2)',
          3: 'var(--color-viz-3)',
          4: 'var(--color-viz-4)',
        },
        /* 强调色 */
        accent: {
          DEFAULT: 'var(--color-accent)',
          hover: 'var(--color-accent-hover)',
        },
      },
      fontFamily: {
        sans: ['"Noto Sans SC"', '"SF Pro Display"', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"SF Mono"', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
        xs: ['0.75rem', { lineHeight: '1rem' }],
        sm: ['0.8125rem', { lineHeight: '1.25rem' }],
        base: ['0.875rem', { lineHeight: '1.5rem' }],
        lg: ['1rem', { lineHeight: '1.75rem' }],
        xl: ['1.125rem', { lineHeight: '1.75rem' }],
        '2xl': ['1.25rem', { lineHeight: '1.875rem' }],
        '3xl': ['1.5rem', { lineHeight: '2rem' }],
        '4xl': ['1.875rem', { lineHeight: '2.25rem' }],
        '5xl': ['2.25rem', { lineHeight: '2.5rem' }],
      },
      spacing: {
        '4.5': '1.125rem',
        '13': '3.25rem',
        '15': '3.75rem',
        '18': '4.5rem',
        '22': '5.5rem',
      },
      borderRadius: {
        '4xl': '2rem',
      },
      boxShadow: {
        'soft': '0 2px 8px var(--shadow-soft)',
        'medium': '0 4px 16px var(--shadow-medium)',
        'heavy': '0 8px 32px var(--shadow-heavy)',
        'glow': '0 0 20px var(--shadow-glow)',
        'inner-soft': 'inset 0 2px 4px var(--shadow-inner)',
        'lift': '0 8px 24px var(--shadow-medium), 0 2px 6px var(--shadow-soft)',
        'card-hover': '0 12px 32px var(--shadow-medium), 0 4px 8px var(--shadow-soft)',
        'focus-ring': '0 0 0 3px var(--color-primary-light)',
        'modal': '0 8px 32px var(--shadow-heavy), 0 4px 8px var(--shadow-medium)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
        'flow': 'flow 3s ease-in-out infinite',
        'flow-dash': 'flowDash 1.5s linear infinite',
        'pulse-ring': 'pulseRing 2s ease-out infinite',
        'shimmer': 'shimmer 2s ease-in-out infinite',
      },
      transitionDuration: {
        '250': '250ms',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
        flow: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        flowDash: {
          '0%': { strokeDashoffset: '27' },
          '100%': { strokeDashoffset: '0' },
        },
        pulseRing: {
          '0%': { opacity: '0.8', transform: 'scale(1)' },
          '100%': { opacity: '0', transform: 'scale(1.3)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '200% 0' },
          '100%': { backgroundPosition: '-200% 0' },
        },
      },
    },
  },
  plugins: [],
}