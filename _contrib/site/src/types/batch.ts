/**
 * Domain Types for Cortex Batch Command Center
 */

import type { BatchStatus, PendingTask } from '../api/types'

export interface EnrichedBatchStatus extends BatchStatus {
  progress_percentage: number
  error_rate: number
  elapsed_seconds: number
  requests_per_second: number
}

export interface EnrichedPendingTask extends PendingTask {
  estimated_duration_minutes: number
  position_in_queue: number
  ai_recommendation?: AIRecommendation
}

export interface AIRecommendation {
  suggestion: 'run_now' | 'reprioritize_up' | 'reprioritize_down' | 'defer' | 'none'
  reason: string
  confidence: number
}

export interface DashboardSummary {
  active_batches: number
  queued_tasks: number
  total_savings_7d: number
  processing_rate: number
}

export interface TimeSeriesPoint {
  timestamp: string
  value: number
  label?: string
}

export interface QueueHealth {
  status: 'healthy' | 'warning' | 'critical'
  message: string
  metrics: {
    avg_wait_time_minutes: number
    oldest_task_age_hours: number
    stuck_tasks: number
  }
}
