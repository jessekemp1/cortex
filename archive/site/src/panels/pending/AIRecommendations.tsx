import { Button } from '@/design-system/components'
import { colors } from '@/design-system/tokens'
import { cn } from '@/utils/cn'

export interface AIRecommendation {
  type: 'run_now' | 'reprioritize_up' | 'reprioritize_down' | 'defer'
  confidence: number
  reason: string
  actionable: boolean
}

interface AIRecommendationsProps {
  recommendation: AIRecommendation
  onAction?: () => void
  className?: string
}

const RECOMMENDATION_CONFIG = {
  run_now: {
    icon: '⚡',
    label: 'RUN NOW',
    color: colors.aiSuggestion,
  },
  reprioritize_up: {
    icon: '⬆️',
    label: 'INCREASE PRIORITY',
    color: colors.aiSuggestion,
  },
  reprioritize_down: {
    icon: '⬇️',
    label: 'DECREASE PRIORITY',
    color: colors.aiSuggestionMuted,
  },
  defer: {
    icon: '⏸️',
    label: 'DEFER',
    color: colors.aiSuggestionMuted,
  },
}

export function AIRecommendations({
  recommendation,
  onAction,
  className,
}: AIRecommendationsProps) {
  const config = RECOMMENDATION_CONFIG[recommendation.type]
  const confidencePercent = Math.round(recommendation.confidence * 100)

  return (
    <div
      className={cn(
        'rounded-lg border-2 p-4',
        'bg-purple-950/20 border-purple-500/30',
        className
      )}
      style={{
        borderColor: `${colors.aiSuggestion}50`,
        backgroundColor: `${colors.aiSuggestion}10`,
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm">🤖</span>
          <span
            className="text-xs font-bold tracking-wider"
            style={{ color: colors.aiSuggestion }}
          >
            AI RECOMMENDATION
          </span>
        </div>
        <span
          className="text-xs font-mono font-bold"
          style={{ color: colors.aiSuggestion }}
        >
          {confidencePercent}%
        </span>
      </div>

      {/* Divider */}
      <div
        className="h-px mb-3"
        style={{ backgroundColor: `${colors.aiSuggestion}30` }}
      />

      {/* Recommendation Type */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-base">{config.icon}</span>
        <span
          className="text-sm font-bold tracking-wide"
          style={{ color: config.color }}
        >
          {config.label}
        </span>
      </div>

      {/* Reason */}
      <p className="text-sm text-gray-300 mb-4 leading-relaxed">
        {recommendation.reason}
      </p>

      {/* Action Button */}
      {recommendation.actionable && onAction && (
        <div className="flex justify-end">
          <Button
            onClick={onAction}
            size="sm"
            variant="primary"
            className="font-mono text-xs"
            style={{
              backgroundColor: colors.aiSuggestion,
              borderColor: colors.aiSuggestion,
            }}
          >
            Execute Now
          </Button>
        </div>
      )}
    </div>
  )
}
