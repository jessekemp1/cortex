import { create } from 'zustand'
import type { Severity } from '@/design-system/components/SeverityIndicator'

interface AnomalyStore {
  severityFilter: Severity | null
  setSeverityFilter: (severity: Severity | null) => void
}

export const useAnomalyStore = create<AnomalyStore>((set) => ({
  severityFilter: null,
  setSeverityFilter: (severity) => set({ severityFilter: severity }),
}))
