import { create } from 'zustand'

interface VortexStore {
  connected: boolean
  selectedModel: string | null
  setConnected: (connected: boolean) => void
  setSelectedModel: (model: string | null) => void
}

export const useVortexStore = create<VortexStore>((set) => ({
  connected: false,
  selectedModel: null,
  setConnected: (connected) => set({ connected }),
  setSelectedModel: (model) => set({ selectedModel: model }),
}))
