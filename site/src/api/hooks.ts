import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { healthApi, batchApi, queueApi, metricsApi } from './client'
import type { PendingTask } from './types'

export const queryKeys = {
  health: ['health'] as const,
  batches: ['batches'] as const,
  batch: (id: string) => ['batch', id] as const,
  queue: ['queue'] as const,
  metrics: (days: number) => ['metrics', days] as const,
}

export function useHealthQuery() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: healthApi.getHealth,
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60,
    retry: 1,
    refetchOnWindowFocus: true,
  })
}

export function useBatchesQuery(limit = 20) {
  return useQuery({
    queryKey: queryKeys.batches,
    queryFn: () => batchApi.listBatches(limit),
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 30,
    retry: 2,
    refetchOnWindowFocus: true,
  })
}

export function useBatchStatusQuery(batchId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.batch(batchId),
    queryFn: () => batchApi.getBatchStatus(batchId),
    enabled: enabled && !!batchId,
    staleTime: 1000 * 5,
    refetchInterval: (query) => {
      if (query.state.data?.status === 'ended') {
        return false
      }
      return 1000 * 5
    },
    retry: 2,
  })
}

export function useQueueQuery() {
  return useQuery({
    queryKey: queryKeys.queue,
    queryFn: queueApi.getQueue,
    staleTime: 1000 * 10,
    refetchInterval: 1000 * 10,
    retry: 2,
    refetchOnWindowFocus: true,
  })
}

export function useMetricsQuery(days = 7) {
  return useQuery({
    queryKey: queryKeys.metrics(days),
    queryFn: () => metricsApi.getMetrics(days),
    staleTime: 1000 * 60 * 5,
    refetchInterval: 1000 * 60 * 5,
    retry: 2,
  })
}

export function useAddTaskMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (task: Omit<PendingTask, 'id' | 'created_at' | 'status'>) =>
      queueApi.addTask(task),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.queue })
    },
  })
}

export function useUpdateTaskPriorityMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      taskId,
      priority,
    }: {
      taskId: string
      priority: PendingTask['priority']
    }) => queueApi.updateTaskPriority(taskId, priority),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.queue })
    },
  })
}

export function useDeleteTaskMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (taskId: string) => queueApi.deleteTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.queue })
    },
  })
}

export function useCancelBatchMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (batchId: string) => batchApi.cancelBatch(batchId),
    onSuccess: (_, batchId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.batch(batchId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.batches })
    },
  })
}

export function usePrefetchBatchStatus() {
  const queryClient = useQueryClient()

  return (batchId: string) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.batch(batchId),
      queryFn: () => batchApi.getBatchStatus(batchId),
      staleTime: 1000 * 5,
    })
  }
}
