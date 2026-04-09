import { useState } from 'react'
import { Card, SectionHeader } from '@/design-system/components'
import { useDocsTreeQuery, useDocContentQuery, useActivityHeatmapQuery } from '@/api/hooks'
import { cn } from '@/utils/cn'

export default function ExploreMode() {
  const [search, setSearch] = useState('')
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set())
  const [rightPanel, setRightPanel] = useState<'heatmap' | 'preview'>('heatmap')

  const { data: docsTree, isLoading: docsLoading } = useDocsTreeQuery()
  const { data: docContent } = useDocContentQuery(selectedPath ?? '', !!selectedPath)
  const { data: heatmap } = useActivityHeatmapQuery()

  const filteredProjects =
    docsTree?.projects
      ?.map((proj) => ({
        ...proj,
        docs: proj.docs.filter(
          (d) =>
            !search ||
            d.doc.toLowerCase().includes(search.toLowerCase()) ||
            d.location.toLowerCase().includes(search.toLowerCase()) ||
            d.purpose.toLowerCase().includes(search.toLowerCase())
        ),
      }))
      .filter((p) => p.docs.length > 0) ?? []

  return (
    <div className="space-y-4 animate-fade-in">
      <SectionHeader
        title="EXPLORE"
        count={docsTree?.total_docs}
        actions={
          <div className="flex items-center gap-1">
            <button
              onClick={() => setRightPanel('heatmap')}
              className={cn(
                'px-2.5 py-1 rounded text-[10px] font-data tracking-wider transition-colors',
                rightPanel === 'heatmap'
                  ? 'bg-cortex-cyan/20 text-cortex-cyan'
                  : 'text-cortex-text-muted hover:text-cortex-text-secondary'
              )}
            >
              ACTIVITY
            </button>
            <button
              onClick={() => setRightPanel('preview')}
              className={cn(
                'px-2.5 py-1 rounded text-[10px] font-data tracking-wider transition-colors',
                rightPanel === 'preview'
                  ? 'bg-cortex-cyan/20 text-cortex-cyan'
                  : 'text-cortex-text-muted hover:text-cortex-text-secondary'
              )}
            >
              PREVIEW
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Left: Docs tree (3 cols) */}
        <div className="lg:col-span-3">
          <input
            type="text"
            placeholder={`Search ${docsTree?.total_docs ?? '...'} docs...`}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full px-3 py-2 bg-cortex-elevated border border-cortex-border rounded-panel font-data text-xs text-cortex-text-primary placeholder:text-cortex-text-muted focus:border-cortex-cyan focus:outline-none"
          />

          <Card variant="default" padding="sm" className="mt-3 max-h-[calc(100vh-250px)] overflow-y-auto">
            {docsLoading ? (
              <p className="font-data text-xs text-cortex-text-muted text-center py-8">
                Loading docs tree...
              </p>
            ) : filteredProjects.length === 0 ? (
              <p className="font-data text-xs text-cortex-text-muted text-center py-8">
                {search ? 'No matching docs found' : 'No docs available'}
              </p>
            ) : (
              filteredProjects.map((proj) => {
                const isExpanded = expandedProjects.has(proj.name) || search.length > 0
                return (
                  <div key={proj.name} className="mb-2">
                    <button
                      onClick={() => {
                        const next = new Set(expandedProjects)
                        if (isExpanded && !search) {
                          next.delete(proj.name)
                        } else {
                          next.add(proj.name)
                        }
                        setExpandedProjects(next)
                      }}
                      className="flex items-center gap-2 w-full px-2 py-1.5 rounded hover:bg-cortex-elevated/50 transition-colors"
                    >
                      <span className="font-data text-[10px] text-cortex-text-muted">
                        {isExpanded ? '\u25BC' : '\u25B6'}
                      </span>
                      <span className="font-data text-xs text-cortex-text-primary font-bold">
                        {proj.name}
                      </span>
                      <span className="font-data text-[10px] text-cortex-text-muted ml-auto">
                        {proj.docs.length}
                      </span>
                    </button>
                    {isExpanded && (
                      <div className="ml-4 space-y-0.5">
                        {proj.docs.map((doc, i) => (
                          <button
                            key={i}
                            onClick={() => {
                              setSelectedPath(doc.location)
                              setRightPanel('preview')
                            }}
                            className={cn(
                              'flex items-center gap-2 w-full px-2 py-1 rounded text-left hover:bg-cortex-elevated/50 transition-colors',
                              selectedPath === doc.location && 'bg-cortex-cyan/10'
                            )}
                          >
                            <span className="font-data text-xs text-cortex-text-secondary truncate">
                              {doc.doc}
                            </span>
                            <span className="font-data text-[10px] text-cortex-text-muted ml-auto truncate max-w-[200px]">
                              {doc.purpose}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </Card>
        </div>

        {/* Right: Heatmap or Preview (2 cols) */}
        <div className="lg:col-span-2">
          <Card
            variant="elevated"
            padding="sm"
            className="max-h-[calc(100vh-250px)] overflow-y-auto"
          >
            {rightPanel === 'heatmap' ? (
              <div>
                <h3 className="font-data text-xs text-cortex-text-muted tracking-wider mb-3">
                  ACTIVITY HOTSPOTS
                </h3>
                {!heatmap?.hotspots || heatmap.hotspots.length === 0 ? (
                  <p className="font-data text-xs text-cortex-text-muted text-center py-8">
                    No activity data available
                  </p>
                ) : (
                  <div className="space-y-1">
                    {heatmap.hotspots.map((f) => {
                      const maxChanges = Math.max(
                        ...(heatmap.hotspots?.map((h) => h.changes_30d) ?? [1])
                      )
                      const pct = (f.changes_30d / maxChanges) * 100
                      return (
                        <div
                          key={f.path}
                          className="relative px-2 py-1.5 rounded overflow-hidden"
                        >
                          <div
                            className="absolute inset-y-0 left-0 bg-cortex-cyan/10 rounded"
                            style={{ width: `${pct}%` }}
                          />
                          <div className="relative flex items-center justify-between">
                            <span className="font-data text-xs text-cortex-text-secondary truncate max-w-[70%]">
                              {f.path}
                            </span>
                            <span className="font-data text-[10px] text-cortex-cyan font-bold">
                              {f.changes_30d}
                            </span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            ) : (
              <div className="p-4">
                {docContent ? (
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-data text-xs text-cortex-text-primary">
                        {docContent.path}
                      </span>
                      <span className="font-data text-[10px] text-cortex-text-muted">
                        {Math.round(docContent.size / 1024)}KB
                      </span>
                    </div>
                    <pre className="font-mono text-xs text-cortex-text-secondary whitespace-pre-wrap leading-relaxed max-h-[calc(100vh-300px)] overflow-y-auto">
                      {docContent.content}
                    </pre>
                  </div>
                ) : (
                  <p className="font-data text-xs text-cortex-text-muted text-center py-8">
                    Select a document to preview
                  </p>
                )}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
