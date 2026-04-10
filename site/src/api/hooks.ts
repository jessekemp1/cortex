import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  healthApi,
  serviceHealthApi,
  batchApi,
  queueApi,
  metricsApi,
  anomalyApi,
  recommendationsApi,
  intelligenceApi,
  projectsApi,
  sessionsApi,
  taskBoardApi,
  conductorApi,
  vortexHealthApi,
  vortexSchedulerApi,
  vortexModelsApi,
  docsApi,
  servicesApi,
  predictionsApi,
  activityApi,
  sessionApi,
  goalsApi,
} from './client'
import type { PendingTask } from './types'
import type { IntelligenceQuery } from '@/types/cortex'
import type { SchedulerStatusRaw } from '@/types/vortex'
import type { Task } from '@/types/task'

export const queryKeys = {
  health: ['health'] as const,
  serviceHealth: ['serviceHealth'] as const,
  batches: ['batches'] as const,
  batch: (id: string) => ['batch', id] as const,
  queue: ['queue'] as const,
  metrics: (days: number) => ['metrics', days] as const,
  anomalies: ['anomalies'] as const,
  recommendations: ['recommendations'] as const,
  projects: ['projects'] as const,
  sessions: ['sessions'] as const,
  taskboard: ['taskboard'] as const,
  conductorHistory: (limit: number) => ['conductor', 'history', limit] as const,
  vortexHealth: ['vortex', 'health'] as const,
  vortexScheduler: ['vortex', 'scheduler'] as const,
  vortexModels: ['vortex', 'models'] as const,
  docsTree: ['docs', 'tree'] as const,
  docContent: (path: string) => ['docs', 'content', path] as const,
  servicesStatus: ['services', 'status'] as const,
  predictions: ['predictions'] as const,
  activityHeatmap: ['activity', 'heatmap'] as const,
  resumeContext: ['session', 'resume-context'] as const,
  staleItems: ['goals', 'stale-items'] as const,
  sessionDelta: ['session', 'delta'] as const,
}

// ── Cortex: Health ──
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

// ── Cortex: Service Health ──
export function useServiceHealthQuery() {
  return useQuery({
    queryKey: queryKeys.serviceHealth,
    queryFn: serviceHealthApi.getServiceHealth,
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 30,
    retry: 1,
    refetchOnWindowFocus: true,
  })
}

// ── Cortex: Batches ──
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
      if (query.state.data?.status === 'ended') return false
      return 1000 * 5
    },
    retry: 2,
  })
}

// ── Cortex: Queue ──
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

// ── Cortex: Metrics ──
export function useMetricsQuery(days = 7) {
  return useQuery({
    queryKey: queryKeys.metrics(days),
    queryFn: () => metricsApi.getMetrics(days),
    staleTime: 1000 * 60 * 5,
    refetchInterval: 1000 * 60 * 5,
    retry: 2,
  })
}

// ── Cortex: Anomalies ──
export function useAnomaliesQuery() {
  return useQuery({
    queryKey: queryKeys.anomalies,
    queryFn: anomalyApi.getAnomalies,
    staleTime: 1000 * 60 * 2,
    refetchInterval: 1000 * 60 * 2,
    retry: 1,
  })
}

// ── Cortex: Recommendations ──
export function useRecommendationsQuery() {
  return useQuery({
    queryKey: queryKeys.recommendations,
    queryFn: recommendationsApi.getRecommendations,
    staleTime: 1000 * 60 * 5,
    refetchInterval: 1000 * 60 * 5,
    retry: 1,
  })
}

// ── Cortex: Intelligence ──
export function useIntelligenceMutation() {
  return useMutation({
    mutationFn: (payload: IntelligenceQuery) => intelligenceApi.query(payload),
  })
}

// ── Cortex: Projects ──
export function useProjectsQuery() {
  return useQuery({
    queryKey: queryKeys.projects,
    queryFn: projectsApi.getProjects,
    staleTime: 1000 * 60 * 2,
    refetchInterval: 1000 * 60 * 2,
    retry: 1,
  })
}

// ── Vortex: Health ──
export function useVortexHealthQuery() {
  return useQuery({
    queryKey: queryKeys.vortexHealth,
    queryFn: vortexHealthApi.getHealth,
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 30,
    retry: 1,
  })
}

// ── Vortex: Scheduler ──
export function useVortexSchedulerQuery() {
  return useQuery<SchedulerStatusRaw>({
    queryKey: queryKeys.vortexScheduler,
    queryFn: vortexSchedulerApi.getScheduler,
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 30,
    retry: 1,
  })
}

// ── Vortex: Models ──
export function useVortexModelsQuery() {
  return useQuery({
    queryKey: queryKeys.vortexModels,
    queryFn: vortexModelsApi.getPerformance,
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60,
    retry: 1,
  })
}

// ── Mutations ──
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
    mutationFn: ({ taskId, priority }: { taskId: string; priority: PendingTask['priority'] }) =>
      queueApi.updateTaskPriority(taskId, priority),
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

// ── Cortex: Sessions ──
export function useSessionsQuery(activeOnly = false) {
  return useQuery({
    queryKey: queryKeys.sessions,
    queryFn: () => sessionsApi.getSessions(activeOnly),
    staleTime: 1000 * 10,
    refetchInterval: 1000 * 15,
    retry: 1,
    refetchOnWindowFocus: true,
  })
}

// ── Cortex: TaskBoard ──
export function useTaskBoardQuery(filters?: { status?: string; project?: string; priority?: string }) {
  return useQuery({
    queryKey: queryKeys.taskboard,
    queryFn: () => taskBoardApi.getTasks(filters),
    staleTime: 1000 * 5,
    refetchInterval: 1000 * 10,
    retry: 2,
    refetchOnWindowFocus: true,
  })
}

export function useCreateTaskBoardTaskMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (task: Parameters<typeof taskBoardApi.createTask>[0]) =>
      taskBoardApi.createTask(task),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.taskboard })
    },
  })
}

export function useUpdateTaskBoardTaskMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      taskId,
      update,
    }: {
      taskId: string
      update: Partial<Pick<Task, 'title' | 'description' | 'status' | 'priority' | 'project' | 'tags' | 'notes'>>
    }) => taskBoardApi.updateTask(taskId, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.taskboard })
    },
  })
}

export function useDeleteTaskBoardTaskMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (taskId: string) => taskBoardApi.deleteTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.taskboard })
    },
  })
}

// ── Conductor: Prompt History ──
export function useConductorHistoryQuery(limit = 5) {
  return useQuery({
    queryKey: queryKeys.conductorHistory(limit),
    queryFn: () => conductorApi.getPromptHistory(limit),
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 60,
    retry: 1,
  })
}

export function useDecomposeTaskMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (req: Parameters<typeof taskBoardApi.decompose>[0]) =>
      taskBoardApi.decompose(req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.taskboard })
    },
  })
}

// ── Co-Navigator: Docs ──
export function useDocsTreeQuery() {
  return useQuery({
    queryKey: queryKeys.docsTree,
    queryFn: docsApi.getTree,
    staleTime: 1000 * 60 * 5,
    refetchInterval: 1000 * 60 * 5,
    retry: 1,
  })
}

export function useDocContentQuery(path: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.docContent(path),
    queryFn: () => docsApi.getContent(path),
    enabled: enabled && !!path,
    staleTime: 1000 * 60,
    retry: 1,
  })
}

// ── Co-Navigator: Services ──
export function useServicesStatusQuery() {
  return useQuery({
    queryKey: queryKeys.servicesStatus,
    queryFn: servicesApi.getStatus,
    staleTime: 1000 * 10,
    refetchInterval: 1000 * 10,
    retry: 1,
    refetchOnWindowFocus: true,
  })
}

// ── Co-Navigator: Predictions ──
export function usePredictionsQuery() {
  return useQuery({
    queryKey: queryKeys.predictions,
    queryFn: predictionsApi.getCurrent,
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60,
    retry: 1,
  })
}

export function useRecordDecisionMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: predictionsApi.recordDecision,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.predictions })
    },
  })
}

// ── Co-Navigator: Activity ──
export function useActivityHeatmapQuery() {
  return useQuery({
    queryKey: queryKeys.activityHeatmap,
    queryFn: activityApi.getHeatmap,
    staleTime: 1000 * 60 * 5,
    refetchInterval: 1000 * 60 * 5,
    retry: 1,
  })
}

// ── Session: Resume Context ──
export function useResumeContextQuery() {
  return useQuery({
    queryKey: queryKeys.resumeContext,
    queryFn: sessionApi.getResumeContext,
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 30,
    retry: 1,
  })
}

// ── Goals: Stale Items ──
export function useStaleItemsQuery() {
  return useQuery({
    queryKey: queryKeys.staleItems,
    queryFn: goalsApi.getStaleItems,
    staleTime: 1000 * 60 * 5,
    refetchInterval: 1000 * 60 * 5,
    retry: 1,
  })
}

// ── Session: Delta ──
export function useSessionDeltaQuery() {
  return useQuery({
    queryKey: queryKeys.sessionDelta,
    queryFn: sessionApi.getDelta,
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60,
    retry: 1,
  })
}
