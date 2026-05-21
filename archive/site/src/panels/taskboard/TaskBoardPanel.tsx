import { useState } from 'react'
import { SectionHeader } from '@/design-system/components/SectionHeader'
import { Button } from '@/design-system/components/Button'
import { useTaskBoardQuery, useCreateTaskBoardTaskMutation } from '@/api/hooks'
import { TaskColumn } from './TaskColumn'
import { DecomposeModal } from './DecomposeModal'
import type { TaskStatus } from '@/types/task'

const STATUS_COLUMNS: TaskStatus[] = ['backlog', 'ready', 'in_progress', 'done']

export default function TaskBoardPanel() {
  const { data, isLoading, error } = useTaskBoardQuery()
  const createMutation = useCreateTaskBoardTaskMutation()
  const [showDecompose, setShowDecompose] = useState(false)
  const [quickAddTitle, setQuickAddTitle] = useState('')

  const tasks = data?.tasks ?? []

  const grouped = STATUS_COLUMNS.reduce(
    (acc, status) => {
      acc[status] = tasks.filter((t) => t.status === status)
      return acc
    },
    {} as Record<TaskStatus, typeof tasks>
  )

  const handleQuickAdd = () => {
    if (!quickAddTitle.trim()) return
    createMutation.mutate(
      { title: quickAddTitle.trim(), status: 'backlog' },
      { onSuccess: () => setQuickAddTitle('') }
    )
  }

  return (
    <div className="p-6 space-y-6">
      <SectionHeader
        title="Task Board"
        count={data?.total}
        actions={
          <Button variant="primary" size="sm" onClick={() => setShowDecompose(true)}>
            DECOMPOSE SPEC
          </Button>
        }
      />

      {/* Quick add bar */}
      <div className="flex gap-2">
        <input
          type="text"
          value={quickAddTitle}
          onChange={(e) => setQuickAddTitle(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleQuickAdd()}
          placeholder="Quick add task to backlog..."
          className="flex-1 px-3 py-2 bg-cortex-elevated border border-cortex-border rounded text-sm font-data text-cortex-text-primary placeholder:text-cortex-text-muted focus:outline-none focus:border-cortex-cyan"
        />
        <Button
          variant="secondary"
          size="sm"
          onClick={handleQuickAdd}
          disabled={!quickAddTitle.trim() || createMutation.isPending}
        >
          ADD
        </Button>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center h-32">
          <div className="w-6 h-6 border-2 border-cortex-cyan border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {error && (
        <div className="text-cortex-critical text-sm font-data p-4 bg-cortex-elevated rounded-panel border border-cortex-critical/30">
          Failed to load tasks: {error.message}
        </div>
      )}

      {!isLoading && !error && (
        <div className="grid grid-cols-4 gap-4">
          {STATUS_COLUMNS.map((status) => (
            <TaskColumn
              key={status}
              status={status}
              tasks={grouped[status]}
              allTasks={tasks}
            />
          ))}
        </div>
      )}

      {/* Decompose modal */}
      {showDecompose && <DecomposeModal onClose={() => setShowDecompose(false)} />}
    </div>
  )
}
