import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { MissionControlLayout } from '@/layouts/MissionControlLayout'
import { CoNavigatorLayout } from '@/layouts/CoNavigatorLayout'

// Co-Navigator mode panels
const BriefingMode = lazy(() => import('@/panels/navigator/BriefingMode'))
const NavigateMode = lazy(() => import('@/panels/navigator/NavigateMode'))
const MonitorMode = lazy(() => import('@/panels/navigator/MonitorMode'))
const ExploreMode = lazy(() => import('@/panels/navigator/ExploreMode'))

// Legacy panels
const OverviewPanel = lazy(() => import('@/panels/overview/OverviewPanel'))
const AnomalyPanel = lazy(() => import('@/panels/anomalies/AnomalyPanel'))
const IntelligencePanel = lazy(() => import('@/panels/intelligence/IntelligencePanel'))
const RecommendationsPanel = lazy(() => import('@/panels/recommendations/RecommendationsPanel'))
const BatchDashboard = lazy(() => import('@/panels/batch/BatchDashboard'))
const MetricsPanel = lazy(() => import('@/panels/metrics/MetricsPanel'))
const VortexHealthPanel = lazy(() => import('@/panels/vortex/VortexHealthPanel'))
const SessionPanel = lazy(() => import('@/panels/sessions/SessionPanel'))
const TaskBoardPanel = lazy(() => import('@/panels/taskboard/TaskBoardPanel'))
const InfrastructurePanel = lazy(() => import('@/panels/infrastructure/InfrastructurePanel'))
const ConductorPanel = lazy(() => import('@/panels/conductor/ConductorPanel'))

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-cortex-cyan border-t-transparent rounded-full animate-spin" />
        <span className="font-data text-xs text-cortex-text-muted tracking-wider">LOADING MODULE</span>
      </div>
    </div>
  )
}

function S({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<LoadingFallback />}>{children}</Suspense>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Co-Navigator (new default) */}
        <Route element={<CoNavigatorLayout />}>
          <Route index element={<S><NavigateMode /></S>} />
          <Route path="briefing" element={<S><BriefingMode /></S>} />
          <Route path="navigate" element={<S><NavigateMode /></S>} />
          <Route path="monitor" element={<S><MonitorMode /></S>} />
          <Route path="explore" element={<S><ExploreMode /></S>} />
        </Route>

        {/* Legacy Mission Control */}
        <Route path="legacy" element={<MissionControlLayout />}>
          <Route index element={<S><OverviewPanel /></S>} />
          <Route path="anomalies" element={<S><AnomalyPanel /></S>} />
          <Route path="intelligence" element={<S><IntelligencePanel /></S>} />
          <Route path="recommendations" element={<S><RecommendationsPanel /></S>} />
          <Route path="batch" element={<S><BatchDashboard /></S>} />
          <Route path="metrics" element={<S><MetricsPanel /></S>} />
          <Route path="vortex" element={<S><VortexHealthPanel /></S>} />
          <Route path="sessions" element={<S><SessionPanel /></S>} />
          <Route path="taskboard" element={<S><TaskBoardPanel /></S>} />
          <Route path="infrastructure" element={<S><InfrastructurePanel /></S>} />
          <Route path="conductor" element={<S><ConductorPanel /></S>} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
