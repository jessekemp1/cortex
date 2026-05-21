/**
 * API Types for Cortex Batch Command Center
 *
 * Response types matching the Cortex backend batch API.
 */

export interface BatchStatus {
  id: string
  status: 'in_progress' | 'validating' | 'finalizing' | 'ended'
  created_at: string
  ended_at?: string
  request_counts: {
    processing: number
    succeeded: number
    errored: number
    expired: number
    canceled: number
  }
}

export interface PendingTask {
  id: string
  title: string
  description: string
  priority: 'CRITICAL' | 'HIGH' | 'NORMAL' | 'LOW'
  status: 'queued' | 'submitted' | 'completed'
  estimated_tokens: number
  submit_after?: string
  deadline?: string
  created_at: string
  source?: string
  blocked_by?: string[]
}

export interface UsageMetrics {
  days: number
  total_tasks: number
  total_tokens: number
  by_priority: Record<string, number>
  by_source?: Record<string, {
    tasks: number
    tokens: number
  }>
  cost_estimate: {
    real_time_would_be: number
    batch_actual: number
    savings: number
  }
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'down'
  version?: string
  timestamp: string
}

export interface APIError {
  error: string
  message: string
  status?: number
}
