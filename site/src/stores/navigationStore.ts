import { create } from 'zustand'

export type PanelId = 'overview' | 'anomalies' | 'intelligence' | 'recommendations' | 'batch' | 'metrics' | 'vortex'

interface NavigationStore {
  activePanelId: PanelId
  sidebarCollapsed: boolean
  setActivePanelId: (id: PanelId) => void
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void
}

export const useNavigationStore = create<NavigationStore>((set) => ({
  activePanelId: 'overview',
  sidebarCollapsed: false,
  setActivePanelId: (id) => set({ activePanelId: id }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
}))
