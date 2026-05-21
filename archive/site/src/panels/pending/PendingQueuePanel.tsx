import { useState, useMemo } from 'react'
import { useQueueQuery } from '@/api/hooks'
import { Card, MetricDisplay } from '@/design-system/components'
import { formatTokens, formatDuration } from '@/utils/formatters'
import { colors } from '@/design-system/tokens'
import { cn } from '@/utils/cn'
import { PendingTaskCard, type PendingTask } from './PendingTaskCard'

type PriorityFilter = 'ALL' | 'CRITICAL' | 'HIGH' | 'NORMAL' | 'LOW'
type SortBy = 'priority' | 'created_at' | 'tokens'

const PRIORITY_ORDER: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  NORMAL: 2,
  LOW: 3,
}

const FILTER_BUTTONS: { value: PriorityFilter; label: string }[] = [
  { value: 'ALL', label: 'ALL' },
  { value: 'CRITICAL', label: 'CRIT' },
  { value: 'HIGH', label: 'HIGH' },
  { value: 'NORMAL', label: 'NORM' },
  { value: 'LOW', label: 'LOW' },
]

const SORT_OPTIONS: { value: SortBy; label: string }[] = [
  { value: 'priority', label: 'Priority' },
  { value: 'created_at', label: 'Created' },
  { value: 'tokens', label: 'Tokens' },
]

export function PendingQueuePanel() {
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('ALL')
  const [sortBy, setSortBy] = useState<SortBy>('priority')

  const { data: queueData, isLoading, error } = useQueueQuery()

  // Process tasks
  const tasks: PendingTask[] = useMemo(() => {
    // Handle various API response shapes
    const rawTasks = (queueData as any)?.jobs || (queueData as any)?.tasks || queueData || []
    if (!Array.isArray(rawTasks)) return []

    return rawTasks.map((task: any, index: number) => ({
      id: task.id || `task-${index}`,
      title: task.title || task.name || 'Untitled Task',
      description: task.description || '',
      priority: task.priority || 'NORMAL',
      tokens: task.tokens || task.estimated_tokens || task.estimated_input_tokens || 0,
      estimated_duration_minutes: task.estimated_duration_minutes || Math.round((task.tokens || task.estimated_tokens || 0) / 100 / 60),
      queue_position: index + 1,
      submit_after: task.submit_after,
      deadline: task.deadline,
      created_at: task.created_at || new Date().toISOString(),
      ai_recommendation: task.ai_recommendation,
    })) as PendingTask[]
  }, [queueData])

  // Filter tasks
  const filteredTasks = useMemo(() => {
    if (priorityFilter === 'ALL') return tasks
    return tasks.filter((task) => task.priority === priorityFilter)
  }, [tasks, priorityFilter])

  // Sort tasks
  const sortedTasks = useMemo(() => {
    const sorted = [...filteredTasks]

    switch (sortBy) {
      case 'priority':
        sorted.sort((a, b) => (PRIORITY_ORDER[a.priority] ?? 99) - (PRIORITY_ORDER[b.priority] ?? 99))
        break
      case 'created_at':
        sorted.sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )
        break
      case 'tokens':
        sorted.sort((a, b) => (b.tokens || 0) - (a.tokens || 0))
        break
    }

    return sorted
  }, [filteredTasks, sortBy])

  // Calculate metrics
  const metrics = useMemo(() => {
    const totalTokens = tasks.reduce((sum, task) => sum + (task.tokens || task.estimated_tokens || 0), 0)
    const totalDuration = tasks.reduce(
      (sum, task) => sum + (task.estimated_duration_minutes || 0),
      0
    )

    return {
      totalTasks: tasks.length,
      totalTokens,
      totalDuration,
    }
  }, [tasks])

  const handleAIAction = (taskId: string) => {
    console.log('AI action for task:', taskId)
    // TODO: Implement AI action execution
  }

  if (error) {
    return (
      <Card className="p-6">
        <div className="text-center">
          <p className="text-red-400 font-mono text-sm">
            Error loading queue: {(error as Error).message}
          </p>
        </div>
      </Card>
    )
  }

  return (
    <Card className="flex flex-col h-full">
      {/* Header */}
      <div
        className="px-6 py-4 border-b flex items-center justify-between"
        style={{ borderColor: `${colors.textMuted}30` }}
      >
        <h2
          className="text-lg font-bold tracking-wider"
          style={{ color: colors.textPrimary }}
        >
          MISSION QUEUE
        </h2>
        <div
          className="flex items-center justify-center w-8 h-8 rounded-full text-xs font-mono font-bold"
          style={{
            backgroundColor: `${colors.accent}20`,
            color: colors.accent,
          }}
        >
          {metrics.totalTasks}
        </div>
      </div>

      {/* Metrics Summary */}
      <div
        className="px-6 py-4 border-b"
        style={{ borderColor: `${colors.textMuted}30` }}
      >
        <div className="grid grid-cols-3 gap-4">
          <MetricDisplay
            label="Tokens"
            value={formatTokens(metrics.totalTokens)}
          />
          <MetricDisplay
            label="Duration"
            value={`~${formatDuration(metrics.totalDuration * 60 * 1000)}`}
          />
          <MetricDisplay
            label="Tasks"
            value={metrics.totalTasks.toString()}
          />
        </div>
      </div>

      {/* Filters and Sort */}
      <div
        className="px-6 py-3 border-b flex items-center justify-between gap-4"
        style={{ borderColor: `${colors.textMuted}30` }}
      >
        {/* Priority Filter Buttons */}
        <div className="flex items-center gap-2">
          {FILTER_BUTTONS.map((filter) => (
            <button
              key={filter.value}
              onClick={() => setPriorityFilter(filter.value)}
              className={cn(
                'px-3 py-1.5 rounded text-xs font-bold tracking-wide transition-all',
                'hover:opacity-80',
                priorityFilter === filter.value
                  ? 'text-gray-900'
                  : 'text-gray-400 bg-transparent'
              )}
              style={{
                backgroundColor:
                  priorityFilter === filter.value
                    ? colors.accent
                    : 'transparent',
                borderWidth: 1,
                borderColor:
                  priorityFilter === filter.value
                    ? colors.accent
                    : `${colors.textMuted}50`,
              }}
            >
              {filter.label}
            </button>
          ))}
        </div>

        {/* Sort Dropdown */}
        <div className="flex items-center gap-2">
          <span
            className="text-xs font-mono"
            style={{ color: colors.textMuted }}
          >
            Sort:
          </span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortBy)}
            className="px-3 py-1.5 rounded text-xs font-mono bg-gray-800 border text-gray-200 focus:outline-none focus:ring-2 focus:ring-purple-500"
            style={{
              borderColor: `${colors.textMuted}50`,
            }}
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Task List */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div
              className="animate-spin rounded-full h-8 w-8 border-b-2"
              style={{ borderColor: colors.accent }}
            />
          </div>
        ) : sortedTasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 space-y-4">
            <div className="text-4xl opacity-50">📋</div>
            <div className="text-center space-y-2">
              <p
                className="text-sm font-semibold"
                style={{ color: colors.textSecondary }}
              >
                {priorityFilter === 'ALL'
                  ? 'No pending tasks'
                  : `No ${priorityFilter.toLowerCase()} priority tasks`}
              </p>
              <p className="text-xs" style={{ color: colors.textMuted }}>
                {priorityFilter === 'ALL'
                  ? 'Your mission queue is clear'
                  : 'Try adjusting your filters'}
              </p>
            </div>
          </div>
        ) : (
          sortedTasks.map((task) => (
            <PendingTaskCard
              key={task.id}
              task={task}
              onAIAction={handleAIAction}
            />
          ))
        )}
      </div>
    </Card>
  )
}
