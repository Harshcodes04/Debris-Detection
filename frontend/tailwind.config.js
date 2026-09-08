/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        marine: {
          950: '#040711',
          900: '#070d1a',
          850: '#0b1326',
          800: '#0f1934',
          750: '#152243',
          700: '#1b2c56',
        },
        ink: '#060a12',
        panel: '#0d1527',
        'panel-light': '#121d36',
        line: '#1e2d4a',
        'line-bright': '#2a3f66',
        muted: '#8094b8',
        wreck: '#00f2ff',
        'wreck-dim': '#0284c7',
        ghost: '#fb7185',
        hazard: '#f59e0b',
        safe: '#34d399',
        intel: '#818cf8',
      },
      animation: {
        'radar-sweep': 'radarSweep 4s linear infinite',
        'sonar-ping': 'sonarPing 2s cubic-bezier(0, 0, 0.2, 1) infinite',
      },
      keyframes: {
        radarSweep: {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
        sonarPing: {
          '75%, 100%': { transform: 'scale(2)', opacity: '0' },
        },
      },
      boxShadow: {
        'glow-cyan': '0 0 20px -3px rgba(0, 242, 255, 0.25)',
        'glow-rose': '0 0 20px -3px rgba(251, 113, 133, 0.25)',
        'glow-emerald': '0 0 20px -3px rgba(52, 211, 153, 0.25)',
      },
    },
  },
  plugins: [],
}

