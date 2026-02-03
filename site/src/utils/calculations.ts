/**
 * Calculation Utilities for Cortex Batch Dashboard
 *
 * Provides functions for computing metrics, progress, and AI recommendations.
 */

import type { BatchStatus, PendingTask } from '../api/types'
import type { AIRecommendation, EnrichedBatchStatus, EnrichedPendingTask } from '../types/batch'

/**
 * Calculate progress percentage from batch request counts
 *
 * @param batch - Batch status from API
 * @returns Progress percentage (0-100)
 */
export function calculateProgress(batch: BatchStatus): number {
  const { processing, succeeded, errored, expired, canceled } = batch.request_counts

  const total = processing + succeeded + errored + expired + canceled
  if (total === 0) return 0

  const completed = succeeded + errored + expired + canceled
  return Math.round((completed / total) * 100)
}

/**
 * Calculate error rate from batch request counts
 *
 * @param batch - Batch status from API
 * @returns Error rate percentage (0-100)
 */
export function calculateErrorRate(batch: BatchStatus): number {
  const { processing, succeeded, errored, expired, canceled } = batch.request_counts

  const total = processing + succeeded + errored + expired + canceled
  if (total === 0) return 0

  return Math.round((errored / total) * 100 * 10) / 10 // One decimal place
}

/**
 * Calculate elapsed time since batch creation
 *
 * @param batch - Batch status from API
 * @returns Elapsed seconds
 */
export function calculateElapsedSeconds(batch: BatchStatus): number {
  const created = new Date(batch.created_at).getTime()
  const now = Date.now()
  return Math.floor((now - created) / 1000)
}

/**
 * Calculate processing rate (requests per second)
 *
 * @param batch - Batch status from API
 * @returns Requests processed per second
 */
export function calculateRequestsPerSecond(batch: BatchStatus): number {
  const elapsed = calculateElapsedSeconds(batch)
  if (elapsed === 0) return 0

  const { succeeded, errored } = batch.request_counts
  const processed = succeeded + errored

  return Math.round((processed / elapsed) * 10) / 10 // One decimal place
}

/**
 * Enrich batch status with computed metrics
 *
 * @param batch - Raw batch status from API
 * @returns Enriched batch status with computed fields
 */
export function enrichBatchStatus(batch: BatchStatus): EnrichedBatchStatus {
  return {
    ...batch,
    progress_percentage: calculateProgress(batch),
    error_rate: calculateErrorRate(batch),
    elapsed_seconds: calculateElapsedSeconds(batch),
    requests_per_second: calculateRequestsPerSecond(batch),
  }
}

/**
 * Estimate task duration based on token count
 *
 * Historical average: ~100 tokens/second for batch processing
 *
 * @param tokens - Estimated token count
 * @returns Estimated duration in minutes
 */
export function estimateDuration(tokens: number): number {
  const TOKENS_PER_SECOND = 100
  const OVERHEAD_FACTOR = 1.2 // 20% overhead for API latency

  const seconds = (tokens / TOKENS_PER_SECOND) * OVERHEAD_FACTOR
  return Math.ceil(seconds / 60)
}

/**
 * Calculate task position in queue based on priority and creation time
 *
 * Priority order: CRITICAL > HIGH > NORMAL > LOW
 * Within same priority, earlier tasks have higher position
 *
 * @param task - Task to calculate position for
 * @param allTasks - All tasks in queue
 * @returns Position (1-indexed, 1 = first in queue)
 */
export function calculateQueuePosition(task: PendingTask, allTasks: PendingTask[]): number {
  const priorityOrder: Record<PendingTask['priority'], number> = {
    CRITICAL: 0,
    HIGH: 1,
    NORMAL: 2,
    LOW: 3,
  }

  // Filter to only queued tasks (not submitted/completed)
  const queuedTasks = allTasks.filter((t) => t.status === 'queued')

  // Sort by priority then creation time
  const sortedTasks = [...queuedTasks].sort((a, b) => {
    const priorityDiff = priorityOrder[a.priority] - priorityOrder[b.priority]
    if (priorityDiff !== 0) return priorityDiff

    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  })

  // Find position (1-indexed)
  const position = sortedTasks.findIndex((t) => t.id === task.id)
  return position === -1 ? sortedTasks.length + 1 : position + 1
}

/**
 * Generate AI recommendation for task scheduling
 *
 * Mock implementation - uses heuristics based on priority, deadline, and queue state.
 * Future: Replace with actual Cortex intelligence API.
 *
 * @param task - Task to generate recommendation for
 * @param allTasks - All tasks in queue (for context)
 * @returns AI recommendation
 */
export function generateRecommendation(
  task: PendingTask,
  allTasks?: PendingTask[]
): AIRecommendation {
  const now = Date.now()

  // Check deadline urgency
  if (task.deadline) {
    const deadline = new Date(task.deadline).getTime()
    const hoursUntilDeadline = (deadline - now) / (1000 * 60 * 60)

    if (hoursUntilDeadline < 2) {
      return {
        suggestion: 'run_now',
        reason: `Deadline in ${Math.floor(hoursUntilDeadline)}h - immediate submission recommended`,
        confidence: 0.95,
      }
    }

    if (hoursUntilDeadline < 6 && task.priority === 'LOW') {
      return {
        suggestion: 'reprioritize_up',
        reason: 'Deadline approaching but priority is LOW - consider upgrading to NORMAL',
        confidence: 0.8,
      }
    }
  }

  // Check if task is blocking others
  const blockedTasks = allTasks?.filter((t) => t.blocked_by?.includes(task.id))
  if (blockedTasks && blockedTasks.length > 0) {
    return {
      suggestion: 'run_now',
      reason: `Blocking ${blockedTasks.length} other task${blockedTasks.length > 1 ? 's' : ''}`,
      confidence: 0.85,
    }
  }

  // Check submit_after constraint
  if (task.submit_after) {
    const submitAfter = new Date(task.submit_after).getTime()
    if (now < submitAfter) {
      const hoursUntilSubmit = (submitAfter - now) / (1000 * 60 * 60)
      return {
        suggestion: 'defer',
        reason: `Scheduled for ${Math.ceil(hoursUntilSubmit)}h from now - wait until submit_after time`,
        confidence: 1.0,
      }
    }
  }

  // Priority-based recommendations
  if (task.priority === 'CRITICAL') {
    return {
      suggestion: 'run_now',
      reason: 'CRITICAL priority - submit immediately',
      confidence: 0.9,
    }
  }

  if (task.priority === 'HIGH') {
    const position = allTasks ? calculateQueuePosition(task, allTasks) : 1
    if (position > 5) {
      return {
        suggestion: 'run_now',
        reason: 'HIGH priority but position in queue is low - consider submitting',
        confidence: 0.7,
      }
    }
  }

  if (task.priority === 'LOW' && !task.deadline) {
    return {
      suggestion: 'defer',
      reason: 'LOW priority with no deadline - can wait for batch orchestration',
      confidence: 0.75,
    }
  }

  // Default: no strong recommendation
  return {
    suggestion: 'none',
    reason: 'Task is appropriately scheduled - monitor queue',
    confidence: 0.5,
  }
}

/**
 * Enrich pending task with computed fields
 *
 * @param task - Raw task from API
 * @param allTasks - All tasks in queue (for position calculation)
 * @returns Enriched task with AI recommendations and metrics
 */
export function enrichPendingTask(
  task: PendingTask,
  allTasks: PendingTask[]
): EnrichedPendingTask {
  return {
    ...task,
    estimated_duration_minutes: estimateDuration(task.estimated_tokens),
    position_in_queue: calculateQueuePosition(task, allTasks),
    ai_recommendation: generateRecommendation(task, allTasks),
  }
}

/**
 * Format duration in human-readable form
 *
 * @param seconds - Duration in seconds
 * @returns Formatted string (e.g., "2h 15m", "45s")
 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}s`
  }

  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) {
    const remainingSeconds = seconds % 60
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`
  }

  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`
}

/**
 * Format token count with K/M suffixes
 *
 * @param tokens - Token count
 * @returns Formatted string (e.g., "1.2K", "3.5M")
 */
export function formatTokens(tokens: number): string {
  if (tokens < 1000) {
    return tokens.toString()
  }

  if (tokens < 1_000_000) {
    return `${(tokens / 1000).toFixed(1)}K`
  }

  return `${(tokens / 1_000_000).toFixed(2)}M`
}

/**
 * Calculate cost savings percentage
 *
 * @param realTimeCost - Cost if run in real-time
 * @param batchCost - Actual batch cost (50% discount)
 * @returns Savings percentage
 */
export function calculateSavingsPercentage(realTimeCost: number, batchCost: number): number {
  if (realTimeCost === 0) return 0
  return Math.round(((realTimeCost - batchCost) / realTimeCost) * 100)
}
