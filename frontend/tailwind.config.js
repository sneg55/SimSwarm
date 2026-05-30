import defaultTheme from 'tailwindcss/defaultTheme.js'
import typography from '@tailwindcss/typography'

export default {
  content: ["./index.html", "./src/**/*.{vue,js}"],
  theme: {
    extend: {
      colors: {
        ocean: {
          abyss: '#0B1426',
          deep: '#0F2035',
          teal: '#164E63',
          cyan: '#0E7490',
          glow: '#22D3EE',
        },
        coral: {
          DEFAULT: '#FF6B6B',
          amber: '#F97316',
          sand: '#FBBF24',
        },
        organic: {
          sage: '#10B981',
          seafoam: '#6EE7B7',
          violet: '#A78BFA',
        },
        mist: {
          foam: '#F1F5F9',
          DEFAULT: '#CBD5E1',
          drift: '#94A3B8',
          slate: '#64748B',
          depth: '#1E293B',
        },
      },
      fontFamily: {
        sans: ['Inter', ...defaultTheme.fontFamily.sans],
        mono: ['JetBrains Mono', ...defaultTheme.fontFamily.mono],
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
        'smooth': 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
      animation: {
        'glow-breathe': 'glow-breathe 3s ease-in-out infinite',
        'shimmer': 'shimmer 2s infinite',
      },
      keyframes: {
        'glow-breathe': {
          '0%, 100%': { opacity: '0.5' },
          '50%': { opacity: '1' },
        },
        'shimmer': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(200%)' },
        },
      },
    },
  },
  plugins: [typography],
}
