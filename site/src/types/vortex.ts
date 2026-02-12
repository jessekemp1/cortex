export interface VortexHealth {
  status: string
  version?: string
  uptime_seconds?: number
  scheduler_running?: boolean
  models_loaded?: string[]
  grib_status?: {
    total_files: number
    latest_file?: string
    last_download?: string
  }
}

export interface SchedulerJob {
  id: string
  name: string
  trigger: string
  next_run?: string
  last_run?: string
  last_status?: 'success' | 'failed' | 'running' | 'unknown'
  enabled: boolean
}

export interface SchedulerStatus {
  running: boolean
  jobs: SchedulerJob[]
  total_jobs: number
}

export interface ModelPerformance {
  model: string
  station: string
  mae_speed: number
  mae_direction: number
  bias_speed: number
  bias_direction: number
  drift_speed?: number
  sample_count: number
  status: 'pass' | 'fail' | 'insufficient_data'
}
