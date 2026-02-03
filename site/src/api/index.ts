export { cortexApi, healthApi, batchApi, queueApi, metricsApi } from './client'
export { default as api } from './client'

export {
  useHealthQuery,
  useBatchesQuery,
  useBatchStatusQuery,
  useQueueQuery,
  useMetricsQuery,
  useAddTaskMutation,
  useUpdateTaskPriorityMutation,
  useDeleteTaskMutation,
  useCancelBatchMutation,
  usePrefetchBatchStatus,
  queryKeys,
} from './hooks'

export type {
  BatchStatus,
  PendingTask,
  UsageMetrics,
  HealthResponse,
  APIError,
} from './types'
