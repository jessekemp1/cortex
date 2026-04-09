import { NavLink, useLocation } from 'react-router-dom'
import { cn } from '@/utils/cn'
import { useNavigationStore } from '@/stores/navigationStore'
import { useHealthQuery } from '@/api/hooks'

interface NavItem {
  path: string
  label: string
  icon: string
}

const navItems: NavItem[] = [
  { path: '/legacy/conductor', label: 'CONDUCTOR', icon: '▷' },
  { path: '/legacy', label: 'OVERVIEW', icon: '◈' },
  { path: '/legacy/anomalies', label: 'ANOMALIES', icon: '⚠' },
  { path: '/legacy/intelligence', label: 'INTEL', icon: '◉' },
  { path: '/legacy/recommendations', label: 'ACTIONS', icon: '▶' },
  { path: '/legacy/batch', label: 'BATCH OPS', icon: '⬡' },
  { path: '/legacy/metrics', label: 'METRICS', icon: '▦' },
  { path: '/legacy/vortex', label: 'VORTEX', icon: '◎' },
  { path: '/legacy/sessions', label: 'SESSIONS', icon: '⊚' },
  { path: '/legacy/taskboard', label: 'TASKS', icon: '⬢' },
  { path: '/legacy/infrastructure', label: 'INFRA', icon: '⬡' },
]

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useNavigationStore()
  const { data: health } = useHealthQuery()
  const location = useLocation()

  const isHealthy = health?.status === 'healthy'

  return (
    <aside
      className={cn(
        'h-full bg-cortex-surface border-r border-cortex-border flex flex-col transition-all duration-200',
        sidebarCollapsed ? 'w-[60px]' : 'w-[220px]'
      )}
    >
      {/* Logo / Title */}
      <div className="flex items-center gap-2 px-3 py-4 border-b border-cortex-border">
        <button
          onClick={toggleSidebar}
          className="w-8 h-8 flex items-center justify-center rounded bg-cortex-cyan-muted text-cortex-cyan font-display text-xs font-bold hover:bg-cortex-cyan/20 transition-colors"
        >
          C
        </button>
        {!sidebarCollapsed && (
          <span className="font-display text-[11px] font-semibold tracking-[0.2em] text-cortex-text-primary truncate">
            CORTEX
          </span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-2 overflow-y-auto">
        {/* Co-Navigator link */}
        <NavLink
          to="/"
          className={cn(
            'flex items-center gap-3 px-3 py-2.5 mx-1 mb-2 rounded text-sm transition-colors',
            'bg-cortex-cyan-muted/50 text-cortex-cyan hover:bg-cortex-cyan-muted border border-cortex-cyan/20'
          )}
        >
          <span className="text-base w-5 text-center">&#9671;</span>
          {!sidebarCollapsed && (
            <span className="font-data text-xs tracking-wider truncate">CO-NAV</span>
          )}
        </NavLink>

        {navItems.map((item) => {
          const isActive = item.path === '/legacy'
            ? location.pathname === '/legacy'
            : location.pathname.startsWith(item.path)

          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 mx-1 rounded text-sm transition-colors group',
                isActive
                  ? 'bg-cortex-cyan-muted text-cortex-cyan'
                  : 'text-cortex-text-secondary hover:text-cortex-text-primary hover:bg-cortex-elevated'
              )}
            >
              <span className={cn('text-base w-5 text-center', isActive && 'text-cortex-cyan')}>
                {item.icon}
              </span>
              {!sidebarCollapsed && (
                <span className="font-data text-xs tracking-wider truncate">{item.label}</span>
              )}
              {isActive && !sidebarCollapsed && (
                <span className="ml-auto w-1 h-4 bg-cortex-cyan rounded-full" />
              )}
            </NavLink>
          )
        })}
      </nav>

      {/* System Status */}
      <div className="p-3 border-t border-cortex-border">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              'w-2 h-2 rounded-full',
              isHealthy ? 'bg-cortex-nominal animate-pulse-slow' : 'bg-cortex-critical animate-pulse-fast'
            )}
          />
          {!sidebarCollapsed && (
            <span className={cn('text-xs font-data', isHealthy ? 'text-cortex-nominal' : 'text-cortex-critical')}>
              {isHealthy ? 'NOMINAL' : 'DEGRADED'}
            </span>
          )}
        </div>
      </div>
    </aside>
  )
}
