import { SectionHeader } from '@/design-system/components'
import { useRecommendationsQuery } from '@/api/hooks'
import { RecommendationCard } from './RecommendationCard'

export default function RecommendationsPanel() {
  const { data, isLoading } = useRecommendationsQuery()
  const recommendations = data?.recommendations ?? []

  const sorted = [...recommendations].sort((a, b) => {
    const order = { HIGH: 0, MEDIUM: 1, LOW: 2 }
    return (order[a.priority] ?? 2) - (order[b.priority] ?? 2)
  })

  return (
    <div className="space-y-6 animate-fade-in">
      <SectionHeader title="Recommended Actions" count={recommendations.length} />

      {isLoading ? (
        <div className="text-center py-8">
          <span className="font-data text-xs text-cortex-text-muted tracking-wider">ANALYZING...</span>
        </div>
      ) : sorted.length === 0 ? (
        <div className="text-center py-12 bg-cortex-elevated rounded-panel border border-cortex-border">
          <span className="font-display text-sm text-cortex-nominal tracking-wider">NO ACTIONS PENDING</span>
          <p className="text-xs text-cortex-text-muted mt-1 font-data">All systems operating within parameters</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sorted.map((rec) => (
            <RecommendationCard key={rec.id} recommendation={rec} />
          ))}
        </div>
      )}
    </div>
  )
}
