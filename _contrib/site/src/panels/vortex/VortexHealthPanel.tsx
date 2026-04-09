import { SectionHeader, PanelContainer } from '@/design-system/components'
import { useVortexHealthQuery, useVortexSchedulerQuery, useVortexModelsQuery } from '@/api/hooks'
import { SchedulerStatusGrid } from './SchedulerStatusGrid'
import { ModelPerformanceTable } from './ModelPerformanceTable'
import { normalizeSchedulerJobs } from '@/types/vortex'
import { cn } from '@/utils/cn'

export default function VortexHealthPanel() {
  const { data: health, isError: healthError } = useVortexHealthQuery()
  const { data: schedulerRaw } = useVortexSchedulerQuery()
  const { data: models } = useVortexModelsQuery()

  const isConnected = !!health && !healthError
  const components = health?.components

  // Normalize scheduler jobs from dict to array
  const schedulerJobs = schedulerRaw ? normalizeSchedulerJobs(schedulerRaw) : []

  return (
    <div className="space-y-6 animate-fade-in">
      <SectionHeader
        title="VortexV2 Health"
        actions={
          <div className="flex items-center gap-2">
            <div className={cn('w-2 h-2 rounded-full', isConnected ? 'bg-cortex-nominal animate-pulse-slow' : 'bg-cortex-critical')} />
            <span className={cn('text-xs font-data', isConnected ? 'text-cortex-nominal' : 'text-cortex-critical')}>
              {isConnected ? 'CONNECTED' : 'OFFLINE'}
            </span>
          </div>
        }
      />

      {!isConnected ? (
        <div className="text-center py-12 bg-cortex-elevated rounded-panel border border-cortex-border">
          <span className="font-display text-sm text-cortex-critical tracking-wider">CONNECTION LOST</span>
          <p className="text-xs text-cortex-text-muted mt-1 font-data">VortexV2 API at :8000 is not responding</p>
        </div>
      ) : (
        <>
          {/* Health summary */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4">
              <div className="text-xs font-data text-cortex-text-muted tracking-wider mb-1">STATUS</div>
              <div className={cn('text-lg font-display font-bold', health.status === 'healthy' ? 'text-cortex-nominal' : 'text-cortex-warning')}>
                {health.status?.toUpperCase()}
              </div>
            </div>
            <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4">
              <div className="text-xs font-data text-cortex-text-muted tracking-wider mb-1">SCHEDULER</div>
              <div className={cn('text-lg font-display font-bold', schedulerRaw?.running ? 'text-cortex-nominal' : 'text-cortex-critical')}>
                {schedulerRaw?.running ? 'RUNNING' : 'STOPPED'}
              </div>
            </div>
            <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4">
              <div className="text-xs font-data text-cortex-text-muted tracking-wider mb-1">JOBS</div>
              <div className="text-lg font-display font-bold text-cortex-cyan tabular-nums">{schedulerRaw?.job_count ?? 0}</div>
            </div>
            <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4">
              <div className="text-xs font-data text-cortex-text-muted tracking-wider mb-1">GRIB DATA</div>
              <div className={cn('text-lg font-display font-bold', components?.grib_data?.status === 'healthy' ? 'text-cortex-nominal' : 'text-cortex-warning')}>
                {components?.grib_data?.files ?? 0} FILES
              </div>
            </div>
            <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4">
              <div className="text-xs font-data text-cortex-text-muted tracking-wider mb-1">MODELS</div>
              <div className="text-lg font-display font-bold text-cortex-cyan tabular-nums">
                {components?.models?.ready ?? 0}/{components?.models?.total ?? 0}
              </div>
            </div>
          </div>

          {/* Component detail */}
          {components && (
            <PanelContainer title="Component Status">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {Object.entries(components).map(([name, comp]) => (
                  <div key={name} className="flex items-center gap-2">
                    <div className={cn(
                      'w-2 h-2 rounded-full',
                      comp.status === 'healthy' ? 'bg-cortex-nominal' :
                      comp.status === 'warming' ? 'bg-cortex-warning animate-pulse' :
                      comp.status === 'degraded' ? 'bg-cortex-warning' : 'bg-cortex-critical'
                    )} />
                    <span className="text-xs font-data text-cortex-text-secondary">
                      {name.toUpperCase().replace('_', ' ')}
                    </span>
                  </div>
                ))}
              </div>
            </PanelContainer>
          )}

          {/* Scheduler Grid */}
          {schedulerJobs.length > 0 && (
            <PanelContainer title="Scheduler Jobs" count={schedulerJobs.length} scanning>
              <SchedulerStatusGrid jobs={schedulerJobs} />
            </PanelContainer>
          )}

          {/* Model Performance */}
          {models && models.length > 0 && (
            <PanelContainer title="Model Performance" count={models.length}>
              <ModelPerformanceTable models={models} />
            </PanelContainer>
          )}
        </>
      )}
    </div>
  )
}
