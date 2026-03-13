import axios, { AxiosError } from 'axios'
import type {
  BatchStatus,
  PendingTask,
  UsageMetrics,
  HealthResponse,
  APIError,
} from './types'
import type { AnomalyResponse, RecommendationResponse, IntelligenceQuery, IntelligenceResult, ProjectStatus } from '@/types/cortex'
import type { VortexHealth, SchedulerStatusRaw, ModelPerformance } from '@/types/vortex'
import type { SessionsResponse } from '@/types/session'
import type { TaskBoardResponse, Task, DecomposeResponse } from '@/types/task'
import type { DocsTreeResponse, DocContentResponse, ServicesStatusResponse, PredictionsResponse, DecisionRecord, ActivityHeatmapResponse } from '@/types/navigator'

const API_BASE_URL = import.meta.env.VITE_CORTEX_API_URL || '/api'

export const cortexApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

cortexApi.interceptors.response.use(
  (response) => response,
  (error: AxiosError<APIError>) => {
    const message = error.response?.data?.message || error.message

    if (error.code === 'ECONNREFUSED') {
      error.message = 'Cortex Bridge is not running. Start with: python cortex/bridge.py'
    } else if (error.response?.status === 404) {
      error.message = `Endpoint not found: ${error.config?.url}`
    } else if (error.response?.status === 500) {
      error.message = `Internal server error: ${message}`
    }

    return Promise.reject(error)
  }
)

// Vortex API — proxied through /vortex → :8000
export const vortexApi = axios.create({
  baseURL: '/vortex-api/api/v2',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Cortex: Health ──
export const healthApi = {
  getHealth: async (): Promise<HealthResponse> => {
    const response = await cortexApi.get('/health')
    // Bridge returns {status, service} — normalize to HealthResponse
    return {
      status: response.data.status === 'healthy' ? 'healthy' : 'degraded',
      timestamp: new Date().toISOString(),
      version: response.data.version,
    }
  },
}

// ── Cortex: Service Health (ecosystem-wide) ──
export const serviceHealthApi = {
  getServiceHealth: async () => {
    const response = await cortexApi.get('/service-health')
    return response.data
  },
}

// ── Cortex: Batches ──
export const batchApi = {
  listBatches: async (limit = 20): Promise<BatchStatus[]> => {
    const response = await cortexApi.get('/batches', { params: { limit } })
    // Bridge wraps in {batches: [...]}
    return response.data.batches ?? response.data
  },

  getBatchStatus: async (batchId: string): Promise<BatchStatus> => {
    const response = await cortexApi.get<BatchStatus>(`/batches/${batchId}`)
    return response.data
  },

  cancelBatch: async (batchId: string): Promise<void> => {
    await cortexApi.post(`/batches/${batchId}/cancel`)
  },
}

// ── Cortex: Queue ──
export const queueApi = {
  getQueue: async (): Promise<PendingTask[]> => {
    const response = await cortexApi.get('/queue')
    // Bridge wraps in {tasks: [...], metadata: {...}}
    return response.data.tasks ?? response.data
  },

  addTask: async (task: Omit<PendingTask, 'id' | 'created_at' | 'status'>): Promise<PendingTask> => {
    const response = await cortexApi.post('/queue', task)
    return response.data.task ?? response.data
  },

  updateTaskPriority: async (
    taskId: string,
    priority: PendingTask['priority']
  ): Promise<PendingTask> => {
    const response = await cortexApi.patch(`/queue/${taskId}`, { priority })
    return response.data.task ?? response.data
  },

  deleteTask: async (taskId: string): Promise<void> => {
    await cortexApi.delete(`/queue/${taskId}`)
  },
}

// ── Cortex: Metrics ──
export const metricsApi = {
  getMetrics: async (days = 7): Promise<UsageMetrics> => {
    const response = await cortexApi.get('/metrics', { params: { days } })
    const d = response.data
    // Bridge returns flat metrics — transform to UsageMetrics shape
    return {
      days: d.period_days ?? days,
      total_tasks: d.total_requests ?? 0,
      total_tokens: 0,
      by_priority: {},
      cost_estimate: {
        real_time_would_be: (d.estimated_savings_usd ?? 0) * 2,
        batch_actual: d.estimated_savings_usd ?? 0,
        savings: d.estimated_savings_usd ?? 0,
      },
    }
  },
}

// ── Cortex: Status / Intelligence / Anomalies / Projects ──
export const statusApi = {
  getStatus: async () => {
    const response = await cortexApi.get('/status')
    return response.data
  },
}

export const intelligenceApi = {
  query: async (payload: IntelligenceQuery): Promise<IntelligenceResult> => {
    const response = await cortexApi.post('/intelligence/query', {
      request: payload.query,
      project: 'cortex',
      query_type: 'analysis',
    })
    const d = response.data
    return {
      query: payload.query,
      response: d.result ?? d.response ?? '',
      confidence: d.confidence ?? 0.5,
      sources: d.sources ?? [],
      reasoning: d.reasoning,
      timestamp: new Date().toISOString(),
    }
  },
}

export const anomalyApi = {
  getAnomalies: async (): Promise<AnomalyResponse> => {
    const response = await cortexApi.get('/anomalies')
    const d = response.data
    // Bridge returns {count, anomalies: [{id, type, severity, title, ...}]}
    const anomalies = (d.anomalies ?? []).map((a: Record<string, unknown>) => ({
      id: a.id ?? '',
      severity: a.severity ?? 'INFO',
      title: a.title ?? '',
      description: a.description ?? '',
      project: (a.type as string)?.toLowerCase() ?? 'cortex',
      detected_at: (a.detected_at as string) ?? new Date().toISOString(),
      recommendation: a.recommendation as string | undefined,
    }))
    const bySeverity: Record<string, number> = {}
    for (const a of anomalies) {
      bySeverity[a.severity] = (bySeverity[a.severity] ?? 0) + 1
    }
    return { anomalies, total: d.count ?? anomalies.length, by_severity: bySeverity }
  },
}

export const recommendationsApi = {
  getRecommendations: async (): Promise<RecommendationResponse> => {
    const response = await cortexApi.get('/recommendations')
    const d = response.data
    // Bridge returns {next_action, risk_alerts, priority_projects, goals_summary}
    // Transform risk_alerts + next_action into Recommendation[]
    const recs: Array<Record<string, unknown>> = []

    if (d.next_action) {
      recs.push({
        id: 'next_action',
        priority: d.next_action.priority === 'HIGH' ? 'HIGH' : d.next_action.priority === 'LOW' ? 'LOW' : 'MEDIUM',
        title: d.next_action.action ?? 'Next Action',
        description: d.next_action.action ?? '',
        project: 'cortex',
        reasoning: `Type: ${d.next_action.type ?? 'maintenance'}`,
        created_at: d.generated_at ?? new Date().toISOString(),
      })
    }

    for (const [i, alert] of (d.risk_alerts ?? []).entries()) {
      recs.push({
        id: `alert_${i}`,
        priority: alert.severity === 'HIGH' ? 'HIGH' : alert.severity === 'MEDIUM' ? 'MEDIUM' : 'LOW',
        title: alert.message ?? 'Risk Alert',
        description: alert.recommendation ?? alert.message ?? '',
        project: 'cortex',
        reasoning: `Type: ${alert.type ?? 'unknown'}`,
        created_at: d.generated_at ?? new Date().toISOString(),
      })
    }

    return { recommendations: recs as unknown as RecommendationResponse['recommendations'], total: recs.length }
  },
}

export const projectsApi = {
  getProjects: async (): Promise<ProjectStatus[]> => {
    const response = await cortexApi.get('/projects')
    // Bridge now returns ProjectStatus[] directly
    return response.data
  },
}

// ── VortexV2: Health (detailed) / Scheduler / Models ──
export const vortexHealthApi = {
  getHealth: async (): Promise<VortexHealth> => {
    const response = await vortexApi.get<VortexHealth>('/health/detailed')
    return response.data
  },
}

export const vortexSchedulerApi = {
  getScheduler: async (): Promise<SchedulerStatusRaw> => {
    const response = await vortexApi.get<SchedulerStatusRaw>('/scheduler/status')
    return response.data
  },
}

export const vortexModelsApi = {
  getPerformance: async (): Promise<ModelPerformance[]> => {
    // Default location: offshore buoy 41002 (South Hatteras)
    const response = await vortexApi.get<ModelPerformance[]>('/models/performance', {
      params: { lat: 32.27, lon: -75.42, days: 7 },
    })
    return response.data
  },
}

// ── Cortex: Sessions ──
export const sessionsApi = {
  getSessions: async (activeOnly = false, limit = 20): Promise<SessionsResponse> => {
    const response = await cortexApi.get('/sessions', {
      params: { active_only: activeOnly, limit },
    })
    return response.data
  },
}

// ── Cortex: TaskBoard ──
export const taskBoardApi = {
  getTasks: async (filters?: {
    status?: string
    project?: string
    priority?: string
  }): Promise<TaskBoardResponse> => {
    const response = await cortexApi.get('/taskboard', { params: filters })
    return response.data
  },

  createTask: async (task: {
    title: string
    description?: string
    status?: string
    priority?: string
    project?: string
    tags?: string[]
    parent_id?: string | null
  }): Promise<{ status: string; task: Task }> => {
    const response = await cortexApi.post('/taskboard', task)
    return response.data
  },

  updateTask: async (
    taskId: string,
    update: Partial<Pick<Task, 'title' | 'description' | 'status' | 'priority' | 'project' | 'tags' | 'notes'>>
  ): Promise<{ status: string; task: Task }> => {
    const response = await cortexApi.patch(`/taskboard/${taskId}`, update)
    return response.data
  },

  deleteTask: async (taskId: string): Promise<void> => {
    await cortexApi.delete(`/taskboard/${taskId}`)
  },

  decompose: async (req: {
    description: string
    project?: string
    context?: string
  }): Promise<DecomposeResponse> => {
    const response = await cortexApi.post('/taskboard/decompose', req)
    return response.data
  },
}

// ── Conductor: Prompt History ──
export interface PromptHistoryEntry {
  timestamp: string
  intent: string
  project_id: string
  intent_level: string
  prompt: string
  token_estimate: number
}

export const conductorApi = {
  getPromptHistory: async (limit = 20): Promise<{ entries: PromptHistoryEntry[]; total: number }> => {
    const response = await cortexApi.get('/conductor/history', { params: { limit } })
    return response.data
  },
}

// ── Co-Navigator: Docs ──
export const docsApi = {
  getTree: async (): Promise<DocsTreeResponse> => {
    const response = await cortexApi.get('/docs/tree')
    return response.data
  },
  getContent: async (path: string): Promise<DocContentResponse> => {
    const response = await cortexApi.get('/docs/content', { params: { path } })
    return response.data
  },
}

// ── Co-Navigator: Services ──
export const servicesApi = {
  getStatus: async (): Promise<ServicesStatusResponse> => {
    const response = await cortexApi.get('/services/status')
    return response.data
  },
}

// ── Co-Navigator: Predictions ──
export const predictionsApi = {
  getCurrent: async (): Promise<PredictionsResponse> => {
    const response = await cortexApi.get('/predictions/current')
    return response.data
  },
  recordDecision: async (decision: {
    prediction_id: string
    scenario_chosen: string
    scenario_name: string
    domain: string
    override_reason?: string
  }): Promise<DecisionRecord> => {
    const response = await cortexApi.post('/decisions/record', decision)
    return response.data
  },
}

// ── Co-Navigator: Activity ──
export const activityApi = {
  getHeatmap: async (): Promise<ActivityHeatmapResponse> => {
    const response = await cortexApi.get('/activity/heatmap')
    return response.data
  },
}

export default {
  health: healthApi,
  serviceHealth: serviceHealthApi,
  batch: batchApi,
  queue: queueApi,
  metrics: metricsApi,
  status: statusApi,
  intelligence: intelligenceApi,
  anomaly: anomalyApi,
  recommendations: recommendationsApi,
  projects: projectsApi,
  sessions: sessionsApi,
  taskBoard: taskBoardApi,
  conductor: conductorApi,
  vortexHealth: vortexHealthApi,
  vortexScheduler: vortexSchedulerApi,
  vortexModels: vortexModelsApi,
  docs: docsApi,
  services: servicesApi,
  predictions: predictionsApi,
  activity: activityApi,
}
