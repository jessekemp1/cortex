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
        cortex: {
          // Background hierarchy (military command center dark)
          bg: '#05050A',
          surface: '#0F1117',
          elevated: '#1A1D27',
          border: '#2A2D3A',

          // Status colors (tactical)
          nominal: '#10B981',       // green - nominal/success
          'nominal-muted': '#065F46',
          warning: '#F59E0B',       // amber - warning/caution
          'warning-muted': '#92400E',
          critical: '#EF4444',      // red - critical/error
          'critical-muted': '#991B1B',
          processing: '#3B82F6',    // blue - processing/active
          'processing-muted': '#1E40AF',
          'ai-suggestion': '#A855F7', // purple - AI suggestions
          'ai-suggestion-muted': '#6B21A8',

          // Text colors
          'text-primary': '#F9FAFB',   // near white
          'text-secondary': '#9CA3AF', // gray-400
          'text-muted': '#6B7280',     // gray-500

          // Accent
          accent: '#8B5CF6',           // violet for highlights
          'accent-muted': '#6D28D9',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        'panel': '8px',
      },
      boxShadow: {
        'panel': '0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -2px rgba(0, 0, 0, 0.3)',
        'elevated': '0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -4px rgba(0, 0, 0, 0.4)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'pulse-fast': 'pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'spin-slow': 'spin 3s linear infinite',
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
      },
    },
  },
  plugins: [],
}
