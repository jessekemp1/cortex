import { SectionHeader } from '@/design-system/components'
import { useIntelligenceMutation } from '@/api/hooks'
import { useIntelligenceStore } from '@/stores/intelligenceStore'
import { QueryInput } from './QueryInput'
import { ResultCard } from './ResultCard'

export default function IntelligencePanel() {
  const mutation = useIntelligenceMutation()
  const { history, selectedResult, addResult, setSelectedResult } = useIntelligenceStore()

  const handleQuery = (query: string) => {
    mutation.mutate(
      { query },
      { onSuccess: (result) => addResult(result) }
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <SectionHeader title="Intelligence Query" />

      <QueryInput onSubmit={handleQuery} isLoading={mutation.isPending} />

      {mutation.isError && (
        <div className="bg-cortex-critical-muted border border-cortex-critical/30 rounded-panel p-3">
          <span className="text-xs font-data text-cortex-critical">
            QUERY FAILED: {mutation.error?.message ?? 'Unknown error'}
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Results list */}
        <div className="xl:col-span-2 space-y-3">
          <SectionHeader title="Results" count={history.length} />
          {history.length === 0 ? (
            <div className="text-center py-12 bg-cortex-elevated rounded-panel border border-cortex-border">
              <span className="font-display text-sm text-cortex-text-muted tracking-wider">AWAITING QUERY</span>
              <p className="text-xs text-cortex-text-muted mt-1 font-data">Enter a query to search Cortex intelligence</p>
            </div>
          ) : (
            history.map((result, i) => (
              <ResultCard
                key={`${result.query}-${i}`}
                result={result}
                isSelected={selectedResult === result}
                onClick={() => setSelectedResult(result)}
              />
            ))
          )}
        </div>

        {/* History sidebar */}
        <div className="space-y-2">
          <SectionHeader title="Query History" count={history.length} />
          <div className="space-y-1">
            {history.map((result, i) => (
              <button
                key={`h-${i}`}
                onClick={() => setSelectedResult(result)}
                className="w-full text-left px-3 py-2 rounded text-xs font-data text-cortex-text-secondary hover:bg-cortex-elevated hover:text-cortex-text-primary transition-colors truncate"
              >
                {result.query}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
