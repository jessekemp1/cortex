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

          // Primary accent — Palantir cyan
          cyan: '#06b6d4',
          'cyan-muted': '#164e63',
          'cyan-glow': 'rgba(6, 182, 212, 0.15)',

          // Status colors (tactical)
          nominal: '#10B981',
          'nominal-muted': '#065F46',
          warning: '#F59E0B',
          'warning-muted': '#92400E',
          critical: '#EF4444',
          'critical-muted': '#991B1B',
          processing: '#3B82F6',
          'processing-muted': '#1E40AF',
          'ai-suggestion': '#A855F7',
          'ai-suggestion-muted': '#6B21A8',

          // Text colors
          'text-primary': '#F9FAFB',
          'text-secondary': '#9CA3AF',
          'text-muted': '#6B7280',

          // Accent (violet — kept for AI suggestions)
          accent: '#8B5CF6',
          'accent-muted': '#6D28D9',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        display: ['Orbitron', 'monospace'],
        data: ['Share Tech Mono', 'monospace'],
      },
      borderRadius: {
        'panel': '8px',
      },
      boxShadow: {
        'panel': '0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -2px rgba(0, 0, 0, 0.3)',
        'elevated': '0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -4px rgba(0, 0, 0, 0.4)',
        'cyan-glow': '0 0 20px rgba(6, 182, 212, 0.15), 0 0 40px rgba(6, 182, 212, 0.05)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'pulse-fast': 'pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'spin-slow': 'spin 3s linear infinite',
        'scan': 'scan 3s ease-in-out infinite',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
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
        scan: {
          '0%': { left: '0%', opacity: '0' },
          '10%': { opacity: '1' },
          '90%': { opacity: '1' },
          '100%': { left: '100%', opacity: '0' },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 5px rgba(6, 182, 212, 0.3)' },
          '50%': { boxShadow: '0 0 20px rgba(6, 182, 212, 0.6)' },
        },
      },
    },
  },
  plugins: [],
}
