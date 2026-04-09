export interface CortexStatus {
  status: 'healthy' | 'degraded' | 'down'
  version?: string
  timestamp: string
  uptime_seconds?: number
  active_batches?: number
  pending_tasks?: number
}

export interface Anomaly {
  id: string
  severity: 'CRITICAL' | 'WARNING' | 'INFO'
  title: string
  description: string
  project: string
  detected_at: string
  recommendation?: string
  resolved?: boolean
}

export interface AnomalyResponse {
  anomalies: Anomaly[]
  total: number
  by_severity: Record<string, number>
}

export interface Recommendation {
  id: string
  priority: 'HIGH' | 'MEDIUM' | 'LOW'
  title: string
  description: string
  project: string
  reasoning: string
  action?: string
  estimated_impact?: string
  created_at: string
}

export interface RecommendationResponse {
  recommendations: Recommendation[]
  total: number
}

export interface IntelligenceQuery {
  query: string
  context?: string
}

export interface IntelligenceResult {
  query: string
  response: string
  confidence: number
  sources: string[]
  reasoning?: string
  timestamp: string
}

export interface ProjectStatus {
  name: string
  status: 'healthy' | 'warning' | 'critical' | 'unknown'
  health_score: number
  last_activity: string
  key_metric?: string
  key_metric_value?: string
}
