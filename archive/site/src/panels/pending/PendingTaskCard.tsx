import { useState } from 'react'
import { Card, PriorityBadge } from '@/design-system/components'
import { formatTokens, formatDuration, formatRelativeTime } from '@/utils/formatters'
import { colors } from '@/design-system/tokens'
import { cn } from '@/utils/cn'
import { AIRecommendations, type AIRecommendation } from './AIRecommendations'

export interface PendingTask {
  id: string
  title: string
  description: string
  priority: 'CRITICAL' | 'HIGH' | 'NORMAL' | 'LOW'
  tokens?: number
  estimated_tokens?: number
  estimated_duration_minutes?: number
  queue_position?: number
  position_in_queue?: number
  submit_after?: string // ISO timestamp
  deadline?: string // ISO timestamp
  ai_recommendation?: AIRecommendation
  created_at: string
  status?: string
  blocked_by?: string[]
}

interface PendingTaskCardProps {
  task: PendingTask
  onAIAction?: (taskId: string) => void
  className?: string
}

function getDeadlineUrgency(deadline: string): {
  color: string
  label: string
} {
  const now = Date.now()
  const deadlineTime = new Date(deadline).getTime()
  const hoursUntil = (deadlineTime - now) / (1000 * 60 * 60)

  if (hoursUntil < 0) {
    return { color: colors.critical, label: 'OVERDUE' }
  } else if (hoursUntil < 1) {
    return { color: colors.critical, label: '< 1h' }
  } else if (hoursUntil < 6) {
    return { color: colors.warning, label: '< 6h' }
  } else {
    return { color: colors.textSecondary, label: formatRelativeTime(new Date(deadline).getTime()) }
  }
}

// Map NORMAL to MEDIUM for PriorityBadge compatibility
function mapPriority(priority: string): 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' {
  if (priority === 'NORMAL') return 'MEDIUM'
  return priority as 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
}

export function PendingTaskCard({
  task,
  onAIAction,
  className,
}: PendingTaskCardProps) {
  const [expanded, setExpanded] = useState(false)

  const deadlineInfo = task.deadline ? getDeadlineUrgency(task.deadline) : null
  const tokenCount = task.tokens || task.estimated_tokens || 0
  const queuePosition = task.queue_position || task.position_in_queue || 0
  const durationMinutes = task.estimated_duration_minutes || Math.round(tokenCount / 100 / 60)

  const truncatedTitle =
    task.title.length > 50 ? `${task.title.slice(0, 50)}...` : task.title

  return (
    <Card className={cn('p-4 space-y-3', className)}>
      {/* Header Row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {/* Queue Position */}
          <span
            className="text-xs font-mono font-bold shrink-0"
            style={{ color: colors.textSecondary }}
          >
            #{queuePosition}
          </span>

          {/* Priority Badge */}
          <PriorityBadge priority={mapPriority(task.priority)} />

          {/* Title */}
          <h3
            className="text-sm font-semibold truncate flex-1"
            style={{ color: colors.textPrimary }}
          >
            {truncatedTitle}
          </h3>
        </div>

        {/* Expand/Collapse Button */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-gray-400 hover:text-gray-200 transition-colors shrink-0"
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          <span className="text-sm">{expanded ? '▲' : '▼'}</span>
        </button>
      </div>

      {/* Metrics Row */}
      <div className="flex items-center gap-4 text-xs font-mono">
        {/* Token Count */}
        <div className="flex items-center gap-1.5">
          <span style={{ color: colors.textSecondary }}>
            {formatTokens(tokenCount)}
          </span>
          <span style={{ color: colors.textMuted }}>tokens</span>
        </div>

        {/* Duration */}
        <div className="flex items-center gap-1.5">
          <span style={{ color: colors.textSecondary }}>~</span>
          <span style={{ color: colors.textSecondary }}>
            {formatDuration(durationMinutes * 60 * 1000)}
          </span>
        </div>

        {/* Deadline */}
        {deadlineInfo && (
          <>
            <span style={{ color: colors.textMuted }}>│</span>
            <div className="flex items-center gap-1.5">
              <span style={{ color: colors.textMuted }}>Deadline:</span>
              <span
                className="font-bold"
                style={{ color: deadlineInfo.color }}
              >
                {deadlineInfo.label}
              </span>
            </div>
          </>
        )}

        {/* Submit After */}
        {task.submit_after && (
          <>
            <span style={{ color: colors.textMuted }}>│</span>
            <div className="flex items-center gap-1.5">
              <span style={{ color: colors.textMuted }}>Submit after:</span>
              <span style={{ color: colors.textSecondary }}>
                {formatRelativeTime(new Date(task.submit_after).getTime())}
              </span>
            </div>
          </>
        )}
      </div>

      {/* AI Recommendation */}
      {task.ai_recommendation && (
        <AIRecommendations
          recommendation={task.ai_recommendation}
          onAction={onAIAction ? () => onAIAction(task.id) : undefined}
        />
      )}

      {/* Expanded Description */}
      {expanded && (
        <div
          className="pt-3 border-t animate-in slide-in-from-top-2 duration-200"
          style={{ borderColor: `${colors.textMuted}30` }}
        >
          <p
            className="text-sm leading-relaxed whitespace-pre-wrap"
            style={{ color: colors.textSecondary }}
          >
            {task.description}
          </p>
        </div>
      )}
    </Card>
  )
}
