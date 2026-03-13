// Co-Navigator types

export type NavigatorMode = 'briefing' | 'navigate' | 'monitor' | 'explore'

export type PredictionDomain = 'dev' | 'architecture' | 'product' | 'qa' | 'release' | 'research'

export interface Scenario {
  name: string
  description: string
  risk: 'low' | 'medium' | 'high'
  effort: string
}

export interface Prediction {
  id: string
  domain: PredictionDomain
  prediction: string
  confidence: number
  evidence: string[]
  scenarios: Scenario[]
}

export interface PredictionsResponse {
  predictions: Prediction[]
  generated_at: string
}

export interface DecisionRecord {
  decision_id: string
  prediction_id: string
  scenario_chosen: string
  scenario_name: string
  domain: string
  override_reason?: string
  timestamp: string
}

export interface DocEntry {
  doc: string
  location: string
  purpose: string
}

export interface DocProject {
  name: string
  docs: DocEntry[]
}

export interface DocsTreeResponse {
  projects: DocProject[]
  total_docs: number
  cached: boolean
}

export interface DocContentResponse {
  path: string
  content: string
  last_modified: string
  size: number
}

export interface LaunchdService {
  label: string
  pid: number | null
  status: number
  healthy: boolean
}

export interface CronJob {
  schedule: string
  command: string
  project: string
}

export interface HealthCheck {
  name: string
  url: string
  status: number
  latency_ms: number
  healthy: boolean
}

export interface ServicesStatusResponse {
  launchd: LaunchdService[]
  cron: CronJob[]
  health: HealthCheck[]
  timestamp: string
}

export interface ActivityFile {
  path: string
  changes_30d: number
  last_changed: string
  project: string
}

export interface ActivityHeatmapResponse {
  files: ActivityFile[]
  hotspots: ActivityFile[]
  period_days: number
}
