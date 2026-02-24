import { SectionHeader, PanelContainer } from '@/design-system/components'
import { useServiceHealthQuery } from '@/api/hooks'
import { cn } from '@/utils/cn'

interface ServiceEntry {
  status: string
  port: number
  label?: string
  version?: string
  models?: number
  stations?: number
  scheduler_jobs?: number
}

const SERVICE_META: Record<string, { label: string; url?: string; description: string }> = {
  bridge: { label: 'Cortex Bridge', description: 'REST API + intelligence layer', url: 'http://localhost:8765' },
  vortex_backend: { label: 'Vortex Backend', description: 'Weather forecast API', url: 'http://localhost:8000' },
  vortex_frontend: { label: 'Vortex UI', description: 'React forecast dashboard', url: 'http://localhost:5173' },
  winfield: { label: 'Winfield', description: 'Marine nowcast engine', url: 'http://localhost:8002' },
  alpha_arena: { label: 'Alpha Arena', description: 'Trading strategy dashboard', url: 'http://localhost:8502' },
  cortex_runtime: { label: 'Cortex Runtime', description: 'Agent execution API', url: 'http://localhost:8003' },
  mission_control: { label: 'Mission Control', description: 'This dashboard', url: 'http://localhost:3001' },
}

function statusColor(status: string) {
  if (status === 'healthy') return 'bg-cortex-nominal'
  if (status === 'degraded') return 'bg-cortex-warning'
  return 'bg-cortex-critical'
}

function statusText(status: string) {
  if (status === 'healthy') return 'text-cortex-nominal'
  if (status === 'degraded') return 'text-cortex-warning'
  return 'text-cortex-critical'
}

function ServiceCard({ name, svc }: { name: string; svc: ServiceEntry }) {
  const meta = SERVICE_META[name]
  const label = meta?.label ?? svc.label ?? name.replace(/_/g, ' ').toUpperCase()
  const description = meta?.description ?? ''
  const url = meta?.url ?? `http://localhost:${svc.port}`
  const isOnline = svc.status !== 'offline'

  return (
    <div className={cn(
      'bg-cortex-elevated border rounded-panel p-4 flex flex-col gap-3 transition-colors',
      svc.status === 'healthy' ? 'border-cortex-border hover:border-cortex-nominal/40' :
      svc.status === 'degraded' ? 'border-cortex-warning/40' :
      'border-cortex-critical/30 opacity-70'
    )}>
      {/* Header row */}
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-0.5">
          <span className="font-display text-sm font-semibold text-cortex-text-primary tracking-wide">
            {label}
          </span>
          <span className="font-data text-[10px] text-cortex-text-muted">{description}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={cn('w-2 h-2 rounded-full', statusColor(svc.status), svc.status === 'healthy' && 'animate-pulse-slow')} />
          <span className={cn('font-data text-[10px] tracking-widest', statusText(svc.status))}>
            {svc.status.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Port + link */}
      <div className="flex items-center justify-between">
        <span className="font-data text-xs text-cortex-text-muted">
          :<span className="text-cortex-cyan tabular-nums">{svc.port}</span>
        </span>
        {isOnline && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-data text-[10px] text-cortex-cyan hover:text-cortex-cyan/70 tracking-wider transition-colors"
          >
            OPEN →
          </a>
        )}
      </div>

      {/* Extra metadata */}
      <div className="flex flex-wrap gap-3">
        {svc.version && (
          <span className="font-data text-[10px] text-cortex-text-muted">
            v<span className="text-cortex-text-secondary">{svc.version}</span>
          </span>
        )}
        {svc.models !== undefined && (
          <span className="font-data text-[10px] text-cortex-text-muted">
            <span className="text-cortex-cyan tabular-nums">{svc.models}</span> models
          </span>
        )}
        {svc.stations !== undefined && (
          <span className="font-data text-[10px] text-cortex-text-muted">
            <span className="text-cortex-cyan tabular-nums">{svc.stations}</span> stations
          </span>
        )}
        {svc.scheduler_jobs !== undefined && (
          <span className="font-data text-[10px] text-cortex-text-muted">
            <span className="text-cortex-cyan tabular-nums">{svc.scheduler_jobs}</span> jobs
          </span>
        )}
      </div>
    </div>
  )
}

export default function InfrastructurePanel() {
  const { data, isError, isLoading } = useServiceHealthQuery()

  const services = data?.services ?? {}
  const overall = data?.overall ?? 'unknown'

  // Sort: healthy first, then degraded, then offline
  const sortedEntries = Object.entries(services as Record<string, ServiceEntry>).sort(([, a], [, b]) => {
    const order = { healthy: 0, degraded: 1, offline: 2 }
    return (order[a.status as keyof typeof order] ?? 3) - (order[b.status as keyof typeof order] ?? 3)
  })

  const healthyCt = sortedEntries.filter(([, s]) => s.status === 'healthy').length
  const totalCt = sortedEntries.filter(([, s]) => 'status' in s).length

  // Pull out tests and emos (not actual services)
  const serviceEntries = sortedEntries.filter(([k]) => !['tests', 'emos'].includes(k))
  const testData = services['tests'] as { total_failures?: number; projects?: Record<string, { passed: number; failed: number }> } | undefined
  const emosData = services['emos'] as { pairs?: Record<string, number>; ready_models?: string[]; threshold?: number } | undefined

  return (
    <div className="space-y-6 animate-fade-in">
      <SectionHeader
        title="Infrastructure"
        actions={
          <div className="flex items-center gap-3">
            {isLoading ? (
              <span className="font-data text-xs text-cortex-text-muted tracking-wider">SCANNING...</span>
            ) : (
              <>
                <div className={cn('w-2 h-2 rounded-full', overall === 'healthy' ? 'bg-cortex-nominal animate-pulse-slow' : 'bg-cortex-warning')} />
                <span className={cn('font-data text-xs tracking-wider', overall === 'healthy' ? 'text-cortex-nominal' : 'text-cortex-warning')}>
                  {healthyCt}/{totalCt} ONLINE
                </span>
              </>
            )}
          </div>
        }
      />

      {isError ? (
        <div className="text-center py-12 bg-cortex-elevated rounded-panel border border-cortex-border">
          <span className="font-display text-sm text-cortex-critical tracking-wider">BRIDGE OFFLINE</span>
          <p className="text-xs text-cortex-text-muted mt-1 font-data">Cannot reach Cortex Bridge at :8765</p>
        </div>
      ) : (
        <>
          {/* Service Grid */}
          <PanelContainer title="Services" count={serviceEntries.length} scanning>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
              {serviceEntries.map(([name, svc]) => (
                <ServiceCard key={name} name={name} svc={svc as ServiceEntry} />
              ))}
            </div>
          </PanelContainer>

          {/* Test Health */}
          {testData?.projects && (
            <PanelContainer title="Test Suite">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(testData.projects).map(([proj, counts]) => (
                  <div key={proj} className="bg-cortex-bg rounded p-3 border border-cortex-border">
                    <div className="font-data text-[10px] text-cortex-text-muted tracking-wider mb-2">
                      {proj.replace(/_/g, ' ').toUpperCase()}
                    </div>
                    <div className="flex items-end gap-2">
                      <span className="font-display text-lg font-bold text-cortex-nominal tabular-nums">{counts.passed}</span>
                      <span className="font-data text-[10px] text-cortex-text-muted mb-0.5">PASS</span>
                      {counts.failed > 0 && (
                        <>
                          <span className="font-display text-lg font-bold text-cortex-critical tabular-nums ml-2">{counts.failed}</span>
                          <span className="font-data text-[10px] text-cortex-text-muted mb-0.5">FAIL</span>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </PanelContainer>
          )}

          {/* EMOS Readiness */}
          {emosData?.pairs && (
            <PanelContainer title="EMOS Model Readiness">
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  {emosData.ready_models?.map(m => (
                    <span key={m} className="px-2 py-1 rounded bg-cortex-nominal-muted text-cortex-nominal font-data text-xs tracking-wider">
                      {m.toUpperCase()} ✓
                    </span>
                  ))}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {Object.entries(emosData.pairs)
                    .filter(([, count]) => count > 0)
                    .sort(([, a], [, b]) => b - a)
                    .map(([model, count]) => {
                      const ready = count >= (emosData.threshold ?? 2000)
                      return (
                        <div key={model} className="flex items-center justify-between bg-cortex-bg rounded px-3 py-2 border border-cortex-border">
                          <span className="font-data text-[10px] text-cortex-text-secondary">{model}</span>
                          <span className={cn('font-data text-xs tabular-nums font-bold', ready ? 'text-cortex-nominal' : 'text-cortex-text-muted')}>
                            {count.toLocaleString()}
                          </span>
                        </div>
                      )
                    })}
                </div>
              </div>
            </PanelContainer>
          )}
        </>
      )}
    </div>
  )
}
