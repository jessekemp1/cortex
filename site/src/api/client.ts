import axios, { AxiosError } from 'axios'
import type {
  BatchStatus,
  PendingTask,
  UsageMetrics,
  HealthResponse,
  APIError,
} from './types'
import type { AnomalyResponse, RecommendationResponse, IntelligenceQuery, IntelligenceResult, ProjectStatus } from '@/types/cortex'
import type { VortexHealth, SchedulerStatus, ModelPerformance } from '@/types/vortex'

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
  baseURL: '/vortex/api/v2',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Cortex: Health ──
export const healthApi = {
  getHealth: async (): Promise<HealthResponse> => {
    const response = await cortexApi.get<HealthResponse>('/health')
    return response.data
  },
}

// ── Cortex: Batches ──
export const batchApi = {
  listBatches: async (limit = 20): Promise<BatchStatus[]> => {
    const response = await cortexApi.get<BatchStatus[]>('/batches', {
      params: { limit },
    })
    return response.data
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
    const response = await cortexApi.get<PendingTask[]>('/queue')
    return response.data
  },

  addTask: async (task: Omit<PendingTask, 'id' | 'created_at' | 'status'>): Promise<PendingTask> => {
    const response = await cortexApi.post<PendingTask>('/queue', task)
    return response.data
  },

  updateTaskPriority: async (
    taskId: string,
    priority: PendingTask['priority']
  ): Promise<PendingTask> => {
    const response = await cortexApi.patch<PendingTask>(`/queue/${taskId}`, {
      priority,
    })
    return response.data
  },

  deleteTask: async (taskId: string): Promise<void> => {
    await cortexApi.delete(`/queue/${taskId}`)
  },
}

// ── Cortex: Metrics ──
export const metricsApi = {
  getMetrics: async (days = 7): Promise<UsageMetrics> => {
    const response = await cortexApi.get<UsageMetrics>('/metrics', {
      params: { days },
    })
    return response.data
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
    const response = await cortexApi.post<IntelligenceResult>('/intelligence/query', payload)
    return response.data
  },
}

export const anomalyApi = {
  getAnomalies: async (): Promise<AnomalyResponse> => {
    const response = await cortexApi.get<AnomalyResponse>('/anomalies')
    return response.data
  },
}

export const recommendationsApi = {
  getRecommendations: async (): Promise<RecommendationResponse> => {
    const response = await cortexApi.get<RecommendationResponse>('/recommendations')
    return response.data
  },
}

export const projectsApi = {
  getProjects: async (): Promise<ProjectStatus[]> => {
    const response = await cortexApi.get<ProjectStatus[]>('/projects')
    return response.data
  },
}

// ── VortexV2: Health / Scheduler / Models ──
export const vortexHealthApi = {
  getHealth: async (): Promise<VortexHealth> => {
    const response = await vortexApi.get<VortexHealth>('/health')
    return response.data
  },
}

export const vortexSchedulerApi = {
  getScheduler: async (): Promise<SchedulerStatus> => {
    const response = await vortexApi.get<SchedulerStatus>('/scheduler/status')
    return response.data
  },
}

export const vortexModelsApi = {
  getPerformance: async (): Promise<ModelPerformance[]> => {
    const response = await vortexApi.get<ModelPerformance[]>('/models/performance')
    return response.data
  },
}

export default {
  health: healthApi,
  batch: batchApi,
  queue: queueApi,
  metrics: metricsApi,
  status: statusApi,
  intelligence: intelligenceApi,
  anomaly: anomalyApi,
  recommendations: recommendationsApi,
  projects: projectsApi,
  vortexHealth: vortexHealthApi,
  vortexScheduler: vortexSchedulerApi,
  vortexModels: vortexModelsApi,
}
