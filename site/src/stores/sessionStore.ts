import { create } from 'zustand'
import type { SessionStatus } from '@/types/session'

interface SessionStore {
  statusFilter: SessionStatus | null
  setStatusFilter: (status: SessionStatus | null) => void
}

export const useSessionStore = create<SessionStore>((set) => ({
  statusFilter: null,
  setStatusFilter: (status) => set({ statusFilter: status }),
}))
