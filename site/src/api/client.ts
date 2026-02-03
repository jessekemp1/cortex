import axios, { AxiosError } from 'axios'
import type {
  BatchStatus,
  PendingTask,
  UsageMetrics,
  HealthResponse,
  APIError,
} from './types'

const API_BASE_URL = import.meta.env.VITE_CORTEX_API_URL || 'http://localhost:8765'

export const cortexApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

cortexApi.interceptors.request.use(
  (config) => {
    console.log(`[CortexAPI] ${config.method?.toUpperCase()} ${config.url}`)
    return config
  },
  (error) => {
    console.error('[CortexAPI] Request error:', error.message)
    return Promise.reject(error)
  }
)

cortexApi.interceptors.response.use(
  (response) => response,
  (error: AxiosError<APIError>) => {
    const message = error.response?.data?.message || error.message
    console.error('[CortexAPI] Request failed:', message)

    if (error.code === 'ECONNREFUSED') {
      error.message = 'Cortex Bridge is not running. Start with: python cortex/bridge.py'
    } else if (error.response?.status === 404) {
      error.message = `Endpoint not found: ${error.config?.url}`
    } else if (error.response?.status === 500) {
      error.message = 'Internal server error. Check Cortex Bridge logs.'
    }

    return Promise.reject(error)
  }
)

export const healthApi = {
  getHealth: async (): Promise<HealthResponse> => {
    const response = await cortexApi.get<HealthResponse>('/health')
    return response.data
  },
}

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

export const metricsApi = {
  getMetrics: async (days = 7): Promise<UsageMetrics> => {
    const response = await cortexApi.get<UsageMetrics>('/metrics', {
      params: { days },
    })
    return response.data
  },
}

export default {
  health: healthApi,
  batch: batchApi,
  queue: queueApi,
  metrics: metricsApi,
}
