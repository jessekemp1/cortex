import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { ScanningBorder } from '@/design-system/components/ScanningBorder'
import { TimeDisplay } from '@/design-system/components/TimeDisplay'
import { useHealthQuery } from '@/api/hooks'
import { useNavigatorStore } from '@/stores/navigatorStore'
import { cn } from '@/utils/cn'
import type { NavigatorMode } from '@/types/navigator'
import { useEffect } from 'react'

const modes: { id: NavigatorMode; label: string; icon: string; key: string }[] = [
  { id: 'briefing', label: 'BRIEFING', icon: '◈', key: '1' },
  { id: 'navigate', label: 'NAVIGATE', icon: '▷', key: '2' },
  { id: 'monitor', label: 'MONITOR', icon: '◎', key: '3' },
  { id: 'explore', label: 'EXPLORE', icon: '⬡', key: '4' },
]

const modeToPath: Record<NavigatorMode, string> = {
  briefing: '/briefing',
  navigate: '/navigate',
  monitor: '/monitor',
  explore: '/explore',
}

const pathToMode: Record<string, NavigatorMode> = {
  '/': 'navigate',
  '/briefing': 'briefing',
  '/navigate': 'navigate',
  '/monitor': 'monitor',
  '/explore': 'explore',
}

export function CoNavigatorLayout() {
  const { data: health } = useHealthQuery()
  const { currentMode, autoMode, setMode } = useNavigatorStore()
  const navigate = useNavigate()
  const location = useLocation()

  const isHealthy = health?.status === 'healthy'

  // Sync URL → store on mount/navigation
  useEffect(() => {
    const modeFromPath = pathToMode[location.pathname]
    if (modeFromPath && modeFromPath !== currentMode) {
      setMode(modeFromPath)
    }
  }, [location.pathname])

  // Keyboard shortcuts: 1-4 for modes
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      const mode = modes.find((m) => m.key === e.key)
      if (mode) {
        setMode(mode.id)
        navigate(modeToPath[mode.id])
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [navigate, setMode])

  const handleModeClick = (mode: NavigatorMode) => {
    setMode(mode)
    navigate(modeToPath[mode])
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-cortex-bg">
      {/* Header */}
      <header className="flex-none border-b border-cortex-border">
        <ScanningBorder />
        <div className="flex items-center justify-between px-4 py-2">
          {/* Left: status */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className={cn(
                'w-2 h-2 rounded-full',
                isHealthy ? 'bg-cortex-nominal animate-pulse-slow' : 'bg-cortex-critical animate-pulse-fast'
              )} />
              <span className={cn(
                'font-data text-xs tracking-wider',
                isHealthy ? 'text-cortex-nominal' : 'text-cortex-critical'
              )}>
                {isHealthy ? 'NOMINAL' : 'DEGRADED'}
              </span>
            </div>
          </div>

          {/* Center: title */}
          <h1 className="font-display text-sm font-semibold tracking-[0.25em] text-cortex-text-primary">
            CORTEX CO-NAVIGATOR
          </h1>

          {/* Right: auto indicator + time */}
          <div className="flex items-center gap-4">
            {autoMode && (
              <span className="px-2 py-0.5 text-xs font-data rounded bg-cortex-ai-suggestion/20 text-cortex-ai-suggestion">
                AUTO
              </span>
            )}
            <TimeDisplay />
          </div>
        </div>

        {/* Mode tabs */}
        <div className="flex items-center gap-1 px-4 pb-2">
          {modes.map((mode) => {
            const isActive = currentMode === mode.id
            return (
              <button
                key={mode.id}
                onClick={() => handleModeClick(mode.id)}
                className={cn(
                  'flex items-center gap-2 px-4 py-1.5 rounded-t text-xs font-data tracking-wider transition-all',
                  isActive
                    ? 'bg-cortex-surface border border-cortex-border border-b-transparent text-cortex-cyan'
                    : 'text-cortex-text-muted hover:text-cortex-text-secondary hover:bg-cortex-surface/50'
                )}
              >
                <span className="text-sm">{mode.icon}</span>
                <span>{mode.label}</span>
                <span className="text-cortex-text-muted text-[10px] ml-1">{mode.key}</span>
              </button>
            )
          })}

          {/* Legacy link */}
          <button
            onClick={() => navigate('/legacy')}
            className="ml-auto text-[10px] font-data text-cortex-text-muted hover:text-cortex-text-secondary tracking-wider"
          >
            LEGACY
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
        <Outlet />
      </main>
    </div>
  )
}
