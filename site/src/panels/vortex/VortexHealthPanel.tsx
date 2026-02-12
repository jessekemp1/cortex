import { SectionHeader, PanelContainer } from '@/design-system/components'
import { useVortexHealthQuery, useVortexSchedulerQuery, useVortexModelsQuery } from '@/api/hooks'
import { SchedulerStatusGrid } from './SchedulerStatusGrid'
import { ModelPerformanceTable } from './ModelPerformanceTable'
import { cn } from '@/utils/cn'

export default function VortexHealthPanel() {
  const { data: health, isError: healthError } = useVortexHealthQuery()
  const { data: scheduler } = useVortexSchedulerQuery()
  const { data: models } = useVortexModelsQuery()

  const isConnected = !!health && !healthError

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
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4">
              <div className="text-xs font-data text-cortex-text-muted tracking-wider mb-1">STATUS</div>
              <div className="text-lg font-display font-bold text-cortex-nominal">{health.status?.toUpperCase()}</div>
            </div>
            <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4">
              <div className="text-xs font-data text-cortex-text-muted tracking-wider mb-1">SCHEDULER</div>
              <div className={cn('text-lg font-display font-bold', scheduler?.running ? 'text-cortex-nominal' : 'text-cortex-critical')}>
                {scheduler?.running ? 'RUNNING' : 'STOPPED'}
              </div>
            </div>
            <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4">
              <div className="text-xs font-data text-cortex-text-muted tracking-wider mb-1">JOBS</div>
              <div className="text-lg font-display font-bold text-cortex-cyan tabular-nums">{scheduler?.total_jobs ?? 0}</div>
            </div>
            <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4">
              <div className="text-xs font-data text-cortex-text-muted tracking-wider mb-1">GRIB FILES</div>
              <div className="text-lg font-display font-bold text-cortex-cyan tabular-nums">{health.grib_status?.total_files ?? 0}</div>
            </div>
          </div>

          {/* Scheduler Grid */}
          {scheduler?.jobs && scheduler.jobs.length > 0 && (
            <PanelContainer title="Scheduler Jobs" count={scheduler.jobs.length} scanning>
              <SchedulerStatusGrid jobs={scheduler.jobs} />
            </PanelContainer>
          )}

          {/* Model Performance */}
          {models && models.length > 0 && (
            <PanelContainer title="Model Performance" count={models.length}>
              <ModelPerformanceTable models={models} />
            </PanelContainer>
          )}

          {/* GRIB Status */}
          {health.grib_status && (
            <PanelContainer title="GRIB Pipeline">
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <span className="text-[10px] font-display tracking-wider text-cortex-text-muted">TOTAL FILES</span>
                  <div className="text-sm font-data text-cortex-cyan tabular-nums mt-0.5">{health.grib_status.total_files}</div>
                </div>
                {health.grib_status.latest_file && (
                  <div>
                    <span className="text-[10px] font-display tracking-wider text-cortex-text-muted">LATEST</span>
                    <div className="text-sm font-data text-cortex-text-secondary truncate mt-0.5">{health.grib_status.latest_file}</div>
                  </div>
                )}
                {health.grib_status.last_download && (
                  <div>
                    <span className="text-[10px] font-display tracking-wider text-cortex-text-muted">LAST DOWNLOAD</span>
                    <div className="text-sm font-data text-cortex-text-secondary mt-0.5">
                      {new Date(health.grib_status.last_download).toLocaleString('en-US', { hour12: false, timeZone: 'UTC' })}
                    </div>
                  </div>
                )}
              </div>
            </PanelContainer>
          )}
        </>
      )}
    </div>
  )
}
