/**
 * Zustand store for batch selection state
 */

import { create } from 'zustand'

interface BatchStore {
  selectedBatchId: string | null
  setSelectedBatchId: (id: string | null) => void
}

export const useBatchStore = create<BatchStore>((set) => ({
  selectedBatchId: null,
  setSelectedBatchId: (id) => set({ selectedBatchId: id }),
}))
