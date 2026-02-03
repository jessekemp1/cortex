/**
 * Cortex Batch Command Center - Main App
 * Military-inspired batch orchestration dashboard
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CommandCenterLayout } from '@/layouts/CommandCenterLayout'
import { StatusBar, BottomActionBar } from '@/panels/shared'
import { RunningPanel } from '@/panels/running'
import { PendingQueuePanel } from '@/panels/pending'
import { CompletedPanel } from '@/panels/completed'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 5000, // Auto-refresh every 5 seconds
      refetchOnWindowFocus: true,
      staleTime: 3000,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <CommandCenterLayout
        statusBar={<StatusBar />}
        bottomBar={<BottomActionBar />}
      >
        {[
          <RunningPanel key="running" />,
          <PendingQueuePanel key="pending" />,
          <CompletedPanel key="completed" />,
        ]}
      </CommandCenterLayout>
    </QueryClientProvider>
  )
}
