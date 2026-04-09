// Matches /api/v2/health/detailed response
export interface VortexHealth {
  status: string
  timestamp: string
  check_duration_ms?: number
  components?: {
    database?: { status: string; latency_ms?: number; error?: string }
    cache?: { status: string; hit_rate?: number; entries?: number }
    grib_data?: { status: string; files?: number; models?: string[] }
    models?: { status: string; ready?: number; total?: number }
    lstm_warmer?: { status: string; is_warmed?: boolean }
  }
}

// Matches /api/v2/scheduler/status response
// Jobs are returned as a dict keyed by job_id, not an array
export interface SchedulerJobRaw {
  name: string
  next_run: string | null
  success_count: number
  failure_count: number
  last_success: string | null
  last_failure: string | null
  last_error: string | null
}

export interface SchedulerStatusRaw {
  running: boolean
  job_count: number
  jobs: Record<string, SchedulerJobRaw>
  timestamp: string
}

// Normalized for UI consumption
export interface SchedulerJob {
  id: string
  name: string
  next_run?: string
  last_run?: string
  last_status: 'success' | 'failed' | 'unknown'
  enabled: boolean
}

export function normalizeSchedulerJobs(raw: SchedulerStatusRaw): SchedulerJob[] {
  return Object.entries(raw.jobs).map(([id, job]) => ({
    id,
    name: job.name,
    next_run: job.next_run ?? undefined,
    last_run: job.last_success ?? job.last_failure ?? undefined,
    last_status: job.last_success
      ? 'success'
      : job.last_failure
        ? 'failed'
        : 'unknown',
    enabled: true,
  }))
}

// Matches /api/v2/models/performance response (per-location, requires lat/lon)
export interface ModelPerformance {
  model: string
  mae: number
  rmse: number
  bias: number
  skillScore: number
  weight: number
  sampleSize: number
}
