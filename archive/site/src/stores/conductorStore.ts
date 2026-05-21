import { create } from 'zustand'
import type { IntentLevel } from '@/types/conductor'

interface ConductorStore {
  // Startup wizard state
  selectedProject: string | null
  intentLevel: IntentLevel
  wizardStep: number

  // Prompt composer state
  userIntent: string
  includeContext: boolean
  selectedTemplate: string | null

  // Actions
  setSelectedProject: (id: string | null) => void
  setIntentLevel: (level: IntentLevel) => void
  setWizardStep: (step: number) => void
  setUserIntent: (intent: string) => void
  setIncludeContext: (include: boolean) => void
  setSelectedTemplate: (id: string | null) => void
  reset: () => void
}

export const useConductorStore = create<ConductorStore>((set) => ({
  selectedProject: null,
  intentLevel: 'collaborative',
  wizardStep: 0,
  userIntent: '',
  includeContext: true,
  selectedTemplate: null,

  setSelectedProject: (id) => set({ selectedProject: id }),
  setIntentLevel: (level) => set({ intentLevel: level }),
  setWizardStep: (step) => set({ wizardStep: step }),
  setUserIntent: (intent) => set({ userIntent: intent }),
  setIncludeContext: (include) => set({ includeContext: include }),
  setSelectedTemplate: (id) => set({ selectedTemplate: id }),
  reset: () => set({
    selectedProject: null,
    intentLevel: 'collaborative',
    wizardStep: 0,
    userIntent: '',
    includeContext: true,
    selectedTemplate: null,
  }),
}))
