import { cn } from '@/utils/cn'
import type { IntelligenceResult } from '@/types/cortex'

interface ResultCardProps {
  result: IntelligenceResult
  isSelected: boolean
  onClick: () => void
}

export function ResultCard({ result, isSelected, onClick }: ResultCardProps) {
  const confidenceColor =
    result.confidence >= 0.8 ? 'text-cortex-nominal' :
    result.confidence >= 0.5 ? 'text-cortex-warning' : 'text-cortex-critical'

  return (
    <div
      onClick={onClick}
      className={cn(
        'bg-cortex-elevated border rounded-panel p-4 cursor-pointer transition-colors',
        isSelected ? 'border-cortex-cyan glow-cyan' : 'border-cortex-border hover:border-cortex-cyan/20'
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-data text-cortex-text-muted truncate max-w-[60%]">{result.query}</span>
        <div className="flex items-center gap-2">
          <span className={cn('text-xs font-data font-semibold', confidenceColor)}>
            {Math.round(result.confidence * 100)}%
          </span>
        </div>
      </div>
      <p className="text-sm text-cortex-text-primary leading-relaxed">{result.response}</p>
      {result.sources.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {result.sources.map((src, i) => (
            <span
              key={i}
              className="px-1.5 py-0.5 text-[10px] font-data rounded bg-cortex-surface text-cortex-text-muted border border-cortex-border"
            >
              {src}
            </span>
          ))}
        </div>
      )}
      {result.reasoning && (
        <div className="mt-2 pt-2 border-t border-cortex-border/50">
          <span className="text-[10px] font-display tracking-wider text-cortex-ai-suggestion">REASONING</span>
          <p className="text-xs text-cortex-text-muted mt-0.5">{result.reasoning}</p>
        </div>
      )}
    </div>
  )
}
