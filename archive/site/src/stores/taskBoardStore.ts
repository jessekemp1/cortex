import { create } from 'zustand'
import type { TaskStatus, TaskPriority } from '@/types/task'

interface TaskBoardStore {
  statusFilter: TaskStatus | null
  projectFilter: string | null
  priorityFilter: TaskPriority | null
  selectedTaskId: string | null
  setStatusFilter: (status: TaskStatus | null) => void
  setProjectFilter: (project: string | null) => void
  setPriorityFilter: (priority: TaskPriority | null) => void
  setSelectedTaskId: (id: string | null) => void
}

export const useTaskBoardStore = create<TaskBoardStore>((set) => ({
  statusFilter: null,
  projectFilter: null,
  priorityFilter: null,
  selectedTaskId: null,
  setStatusFilter: (status) => set({ statusFilter: status }),
  setProjectFilter: (project) => set({ projectFilter: project }),
  setPriorityFilter: (priority) => set({ priorityFilter: priority }),
  setSelectedTaskId: (id) => set({ selectedTaskId: id }),
}))
