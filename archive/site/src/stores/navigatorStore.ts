import { create } from 'zustand'
import type { NavigatorMode } from '@/types/navigator'

interface NavigatorStore {
  currentMode: NavigatorMode
  autoMode: boolean
  setMode: (mode: NavigatorMode) => void
  setAutoMode: (auto: boolean) => void
}

function getAutoMode(): NavigatorMode {
  const hour = new Date().getHours()
  if (hour >= 6 && hour < 10) return 'briefing'
  if (hour >= 22 || hour < 6) return 'monitor'
  return 'navigate'
}

export const useNavigatorStore = create<NavigatorStore>((set) => ({
  currentMode: getAutoMode(),
  autoMode: true,
  setMode: (mode) => set({ currentMode: mode, autoMode: false }),
  setAutoMode: (auto) => set((s) => ({
    autoMode: auto,
    currentMode: auto ? getAutoMode() : s.currentMode,
  })),
}))
