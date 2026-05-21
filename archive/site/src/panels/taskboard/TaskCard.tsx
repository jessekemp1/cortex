import { useState } from 'react'
import { Card } from '@/design-system/components/Card'
import { cn } from '@/utils/cn'
import type { Task, TaskStatus } from '@/types/task'
import { TASK_STATUS_COLORS, TASK_STATUS_LABELS, PROJECT_COLORS } from '@/types/task'
import { useUpdateTaskBoardTaskMutation, useDeleteTaskBoardTaskMutation } from '@/api/hooks'

const STATUS_ORDER: TaskStatus[] = ['backlog', 'ready', 'in_progress', 'done']

const PRIORITY_ICONS: Record<string, string> = {
  HIGH: '▲',
  MEDIUM: '●',
  LOW: '▽',
}

const PRIORITY_COLORS: Record<string, string> = {
  HIGH: '#F59E0B',
  MEDIUM: '#3B82F6',
  LOW: '#6B7280',
}

interface TaskCardProps {
  task: Task
  allTasks: Task[]
}

export function TaskCard({ task, allTasks }: TaskCardProps) {
  const [expanded, setExpanded] = useState(false)
  const updateMutation = useUpdateTaskBoardTaskMutation()
  const deleteMutation = useDeleteTaskBoardTaskMutation()

  const projectColor = PROJECT_COLORS[task.project] ?? '#6B7280'
  const priorityColor = PRIORITY_COLORS[task.priority] ?? '#6B7280'

  // Count completed subtasks
  const subtaskIds = task.subtasks ?? []
  const subtasksDone = subtaskIds.filter((id) =>
    allTasks.find((t) => t.id === id && t.status === 'done')
  ).length

  const handleStatusChange = (newStatus: TaskStatus) => {
    updateMutation.mutate({ taskId: task.id, update: { status: newStatus } })
  }

  return (
    <Card variant="default" padding="none" className="overflow-hidden">
      <div
        className="p-3 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        {/* Title + priority */}
        <div className="flex items-start gap-2 mb-2">
          <span style={{ color: priorityColor }} className="text-xs mt-0.5" title={task.priority}>
            {PRIORITY_ICONS[task.priority]}
          </span>
          <span className="font-data text-sm text-cortex-text-primary leading-tight line-clamp-2">
            {task.title}
          </span>
        </div>

        {/* Project badge + tags */}
        <div className="flex items-center gap-1.5 flex-wrap mb-2">
          {task.project && (
            <span
              className="px-1.5 py-0.5 text-[9px] font-mono font-medium uppercase tracking-wider rounded border"
              style={{ borderColor: projectColor, color: projectColor }}
            >
              {task.project}
            </span>
          )}
          {task.tags.slice(0, 2).map((tag) => (
            <span
              key={tag}
              className="px-1.5 py-0.5 text-[9px] font-data text-cortex-text-muted bg-cortex-elevated rounded"
            >
              {tag}
            </span>
          ))}
        </div>

        {/* Subtask progress */}
        {subtaskIds.length > 0 && (
          <div className="flex items-center gap-2 mb-1">
            <div className="flex-1 h-1 bg-cortex-elevated rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${(subtasksDone / subtaskIds.length) * 100}%`,
                  backgroundColor: TASK_STATUS_COLORS.done,
                }}
              />
            </div>
            <span className="text-[9px] font-data text-cortex-text-muted tabular-nums">
              {subtasksDone}/{subtaskIds.length}
            </span>
          </div>
        )}
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t border-cortex-border space-y-2">
          {task.description && (
            <p className="text-xs text-cortex-text-secondary font-data leading-relaxed">
              {task.description}
            </p>
          )}

          {/* Status change */}
          <div className="flex items-center gap-1">
            <span className="text-[9px] font-data text-cortex-text-muted mr-1">STATUS:</span>
            {STATUS_ORDER.map((s) => (
              <button
                key={s}
                onClick={(e) => {
                  e.stopPropagation()
                  handleStatusChange(s)
                }}
                className={cn(
                  'px-1.5 py-0.5 text-[9px] font-mono uppercase tracking-wider rounded border transition-colors',
                  task.status === s
                    ? 'bg-cortex-elevated'
                    : 'bg-transparent border-transparent text-cortex-text-muted hover:text-cortex-text-secondary'
                )}
                style={
                  task.status === s
                    ? { borderColor: TASK_STATUS_COLORS[s], color: TASK_STATUS_COLORS[s] }
                    : undefined
                }
              >
                {TASK_STATUS_LABELS[s]}
              </button>
            ))}
          </div>

          {/* Delete */}
          <button
            onClick={(e) => {
              e.stopPropagation()
              deleteMutation.mutate(task.id)
            }}
            className="text-[9px] font-mono text-cortex-text-muted hover:text-cortex-critical transition-colors"
          >
            DELETE
          </button>
        </div>
      )}
    </Card>
  )
}
