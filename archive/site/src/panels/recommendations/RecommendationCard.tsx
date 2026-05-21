import { cn } from '@/utils/cn'
import type { Recommendation } from '@/types/cortex'

const priorityConfig: Record<string, { bg: string; text: string }> = {
  HIGH: { bg: 'bg-cortex-warning-muted', text: 'text-cortex-warning' },
  MEDIUM: { bg: 'bg-cortex-processing-muted', text: 'text-cortex-processing' },
  LOW: { bg: 'bg-cortex-surface', text: 'text-cortex-text-secondary' },
}

interface RecommendationCardProps {
  recommendation: Recommendation
}

export function RecommendationCard({ recommendation: rec }: RecommendationCardProps) {
  const pConfig = priorityConfig[rec.priority] || priorityConfig.LOW!

  return (
    <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4 border-l-[3px] border-l-cortex-ai-suggestion hover:border-cortex-ai-suggestion/30 transition-colors">
      <div className="flex items-center gap-2 mb-2">
        <span className={cn('px-2 py-0.5 text-[10px] font-display tracking-wider rounded', pConfig.bg, pConfig.text)}>
          {rec.priority}
        </span>
        <span className="px-1.5 py-0.5 text-[10px] font-data rounded bg-cortex-surface text-cortex-text-muted border border-cortex-border">
          {rec.project}
        </span>
      </div>
      <h4 className="text-sm font-semibold text-cortex-text-primary mb-1">{rec.title}</h4>
      <p className="text-xs text-cortex-text-secondary leading-relaxed mb-2">{rec.description}</p>
      {rec.reasoning && (
        <div className="mt-2 pt-2 border-t border-cortex-border/50">
          <span className="text-[10px] font-display tracking-wider text-cortex-ai-suggestion">REASONING</span>
          <p className="text-xs text-cortex-text-muted mt-0.5">{rec.reasoning}</p>
        </div>
      )}
      {rec.action && (
        <div className="mt-2">
          <code className="text-xs font-mono text-cortex-cyan bg-cortex-surface px-2 py-1 rounded border border-cortex-border">
            {rec.action}
          </code>
        </div>
      )}
    </div>
  )
}
