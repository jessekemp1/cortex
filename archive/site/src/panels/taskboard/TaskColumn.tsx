import type { Task, TaskStatus } from '@/types/task'
import { TASK_STATUS_COLORS, TASK_STATUS_LABELS } from '@/types/task'
import { TaskCard } from './TaskCard'

interface TaskColumnProps {
  status: TaskStatus
  tasks: Task[]
  allTasks: Task[]
}

export function TaskColumn({ status, tasks, allTasks }: TaskColumnProps) {
  const color = TASK_STATUS_COLORS[status]

  return (
    <div className="space-y-3">
      {/* Column header */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
          <span className="text-[11px] font-display font-semibold tracking-[0.15em] uppercase text-cortex-text-secondary">
            {TASK_STATUS_LABELS[status]}
          </span>
        </div>
        <span className="text-[10px] font-data text-cortex-text-muted tabular-nums">
          {tasks.length}
        </span>
      </div>

      {/* Cards */}
      <div className="space-y-2">
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} allTasks={allTasks} />
        ))}
        {tasks.length === 0 && (
          <div className="p-4 text-center text-[10px] font-data text-cortex-text-muted border border-dashed border-cortex-border rounded-panel">
            No tasks
          </div>
        )}
      </div>
    </div>
  )
}
