import { create } from 'zustand'
import type { IntelligenceResult } from '@/types/cortex'

interface IntelligenceStore {
  queryText: string
  history: IntelligenceResult[]
  selectedResult: IntelligenceResult | null
  setQueryText: (text: string) => void
  addResult: (result: IntelligenceResult) => void
  setSelectedResult: (result: IntelligenceResult | null) => void
  clearHistory: () => void
}

export const useIntelligenceStore = create<IntelligenceStore>((set) => ({
  queryText: '',
  history: [],
  selectedResult: null,
  setQueryText: (text) => set({ queryText: text }),
  addResult: (result) =>
    set((s) => ({ history: [result, ...s.history].slice(0, 50), selectedResult: result })),
  setSelectedResult: (result) => set({ selectedResult: result }),
  clearHistory: () => set({ history: [], selectedResult: null }),
}))
