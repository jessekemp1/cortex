import { cn } from '@/utils/cn'
import type { ModelPerformance } from '@/types/vortex'

interface ModelPerformanceTableProps {
  models: ModelPerformance[]
}

export function ModelPerformanceTable({ models }: ModelPerformanceTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-data">
        <thead>
          <tr className="border-b border-cortex-border">
            <th className="text-left py-2 px-3 font-display text-[10px] tracking-wider text-cortex-text-muted">MODEL</th>
            <th className="text-right py-2 px-3 font-display text-[10px] tracking-wider text-cortex-text-muted">MAE (kt)</th>
            <th className="text-right py-2 px-3 font-display text-[10px] tracking-wider text-cortex-text-muted">RMSE</th>
            <th className="text-right py-2 px-3 font-display text-[10px] tracking-wider text-cortex-text-muted">BIAS</th>
            <th className="text-right py-2 px-3 font-display text-[10px] tracking-wider text-cortex-text-muted">SKILL</th>
            <th className="text-right py-2 px-3 font-display text-[10px] tracking-wider text-cortex-text-muted">WEIGHT</th>
            <th className="text-right py-2 px-3 font-display text-[10px] tracking-wider text-cortex-text-muted">SAMPLES</th>
          </tr>
        </thead>
        <tbody>
          {models.map((m) => (
            <tr key={m.model} className="border-b border-cortex-border/50 hover:bg-cortex-elevated/50">
              <td className="py-2 px-3 text-cortex-text-primary font-semibold">{m.model}</td>
              <td className="py-2 px-3 text-right tabular-nums text-cortex-cyan">{m.mae.toFixed(2)}</td>
              <td className="py-2 px-3 text-right tabular-nums text-cortex-text-secondary">{m.rmse.toFixed(2)}</td>
              <td className={cn('py-2 px-3 text-right tabular-nums', Math.abs(m.bias) > 1 ? 'text-cortex-warning' : 'text-cortex-text-secondary')}>
                {m.bias > 0 ? '+' : ''}{m.bias.toFixed(2)}
              </td>
              <td className={cn('py-2 px-3 text-right tabular-nums', m.skillScore > 0 ? 'text-cortex-nominal' : 'text-cortex-critical')}>
                {(m.skillScore * 100).toFixed(0)}%
              </td>
              <td className="py-2 px-3 text-right tabular-nums text-cortex-text-muted">{(m.weight * 100).toFixed(0)}%</td>
              <td className="py-2 px-3 text-right tabular-nums text-cortex-text-muted">{m.sampleSize}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
