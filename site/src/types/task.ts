export type TaskStatus = 'backlog' | 'ready' | 'in_progress' | 'done'
export type TaskPriority = 'HIGH' | 'MEDIUM' | 'LOW'

export interface Task {
  id: string
  title: string
  description: string
  status: TaskStatus
  priority: TaskPriority
  project: string
  tags: string[]
  parent_id: string | null
  subtasks: string[]
  created_at: string
  updated_at: string
  started_at: string | null
  completed_at: string | null
  source: string
  notes: string
}

export interface TaskBoardResponse {
  tasks: Task[]
  total: number
}

export interface DecomposeResponse {
  parent_task: Task
  subtasks: Task[]
  ai_response: string
}

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  backlog: 'BACKLOG',
  ready: 'READY',
  in_progress: 'IN PROGRESS',
  done: 'DONE',
}

export const TASK_STATUS_COLORS: Record<TaskStatus, string> = {
  backlog: '#6B7280',
  ready: '#3B82F6',
  in_progress: '#F59E0B',
  done: '#10B981',
}

export const PROJECT_COLORS: Record<string, string> = {
  VortexV2: '#06b6d4',
  VortexV3: '#3B82F6',
  Cortex: '#A855F7',
  Winfield: '#10B981',
  'Alpha Arena': '#F59E0B',
}
