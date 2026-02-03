/**
 * Cortex Batch Command Center Design Tokens
 * Military/Tactical Command Center Theme
 * Inspired by Anduril Lattice and mission control interfaces
 */

export const colors = {
  // Background hierarchy (near black military aesthetic)
  bg: '#05050A',
  surface: '#0F1117',
  elevated: '#1A1D27',
  border: '#2A2D3A',

  // Status colors (tactical operations)
  nominal: '#10B981',           // green - systems nominal
  nominalMuted: '#065F46',
  warning: '#F59E0B',           // amber - attention required
  warningMuted: '#92400E',
  critical: '#EF4444',          // red - critical alert
  criticalMuted: '#991B1B',
  processing: '#3B82F6',        // blue - processing/active
  processingMuted: '#1E40AF',
  aiSuggestion: '#A855F7',      // purple - AI recommendations
  aiSuggestionMuted: '#6B21A8',

  // Text hierarchy
  textPrimary: '#F9FAFB',       // near white
  textSecondary: '#9CA3AF',     // gray-400
  textMuted: '#6B7280',         // gray-500

  // Accent
  accent: '#8B5CF6',            // violet
  accentMuted: '#6D28D9',
} as const

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  '2xl': 48,
  panelGap: 16,
  sectionGap: 24,
} as const

export const typography = {
  fontFamily: {
    sans: 'Inter, system-ui, sans-serif',
    mono: 'JetBrains Mono, monospace',
  },
  fontSize: {
    xs: '0.75rem',      // 12px
    sm: '0.875rem',     // 14px
    base: '1rem',       // 16px
    lg: '1.125rem',     // 18px
    xl: '1.25rem',      // 20px
    '2xl': '1.5rem',    // 24px
    '3xl': '1.875rem',  // 30px
    metric: '2.5rem',   // 40px - for large metrics
    hero: '3rem',       // 48px - for hero metrics
  },
  fontWeight: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
} as const

export const animation = {
  fast: '150ms',
  normal: '300ms',
  slow: '500ms',
  pulse: '1500ms',
  easing: {
    default: 'cubic-bezier(0.4, 0, 0.2, 1)',
    in: 'cubic-bezier(0.4, 0, 1, 1)',
    out: 'cubic-bezier(0, 0, 0.2, 1)',
    inOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
  },
} as const

// Priority levels for batch jobs
export const priorityLevels = {
  CRITICAL: 'CRITICAL',
  HIGH: 'HIGH',
  MEDIUM: 'MEDIUM',
  LOW: 'LOW',
} as const

export type PriorityLevel = keyof typeof priorityLevels

// Status types for batch jobs
export const statusTypes = {
  QUEUED: 'QUEUED',
  PROCESSING: 'PROCESSING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  CANCELLED: 'CANCELLED',
} as const

export type StatusType = keyof typeof statusTypes

/**
 * Get color for priority level
 */
export function getPriorityColor(priority: PriorityLevel): string {
  switch (priority) {
    case 'CRITICAL':
      return colors.critical
    case 'HIGH':
      return colors.warning
    case 'MEDIUM':
      return colors.processing
    case 'LOW':
      return colors.textSecondary
  }
}

/**
 * Get color for status type
 */
export function getStatusColor(status: StatusType): string {
  switch (status) {
    case 'QUEUED':
      return colors.textSecondary
    case 'PROCESSING':
      return colors.processing
    case 'COMPLETED':
      return colors.nominal
    case 'FAILED':
      return colors.critical
    case 'CANCELLED':
      return colors.textMuted
  }
}

/**
 * Check if status is active (should show pulse animation)
 */
export function isActiveStatus(status: StatusType): boolean {
  return status === 'PROCESSING' || status === 'QUEUED'
}
