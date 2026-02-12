import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { MissionControlLayout } from '@/layouts/MissionControlLayout'

const OverviewPanel = lazy(() => import('@/panels/overview/OverviewPanel'))
const AnomalyPanel = lazy(() => import('@/panels/anomalies/AnomalyPanel'))
const IntelligencePanel = lazy(() => import('@/panels/intelligence/IntelligencePanel'))
const RecommendationsPanel = lazy(() => import('@/panels/recommendations/RecommendationsPanel'))
const BatchDashboard = lazy(() => import('@/panels/batch/BatchDashboard'))
const MetricsPanel = lazy(() => import('@/panels/metrics/MetricsPanel'))
const VortexHealthPanel = lazy(() => import('@/panels/vortex/VortexHealthPanel'))

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

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<MissionControlLayout />}>
          <Route index element={<Suspense fallback={<LoadingFallback />}><OverviewPanel /></Suspense>} />
          <Route path="anomalies" element={<Suspense fallback={<LoadingFallback />}><AnomalyPanel /></Suspense>} />
          <Route path="intelligence" element={<Suspense fallback={<LoadingFallback />}><IntelligencePanel /></Suspense>} />
          <Route path="recommendations" element={<Suspense fallback={<LoadingFallback />}><RecommendationsPanel /></Suspense>} />
          <Route path="batch" element={<Suspense fallback={<LoadingFallback />}><BatchDashboard /></Suspense>} />
          <Route path="metrics" element={<Suspense fallback={<LoadingFallback />}><MetricsPanel /></Suspense>} />
          <Route path="vortex" element={<Suspense fallback={<LoadingFallback />}><VortexHealthPanel /></Suspense>} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
