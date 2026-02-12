import { SectionHeader } from '@/design-system/components'
import { RunningPanel } from '@/panels/running'
import { PendingQueuePanel } from '@/panels/pending'
import { CompletedPanel } from '@/panels/completed'

export default function BatchDashboard() {
  return (
    <div className="space-y-6 animate-fade-in">
      <SectionHeader title="Batch Operations" />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Running (25%) */}
        <div className="lg:col-span-3">
          <RunningPanel />
        </div>

        {/* Pending (50%) */}
        <div className="lg:col-span-6">
          <PendingQueuePanel />
        </div>

        {/* Completed (25%) */}
        <div className="lg:col-span-3">
          <CompletedPanel />
        </div>
      </div>
    </div>
  )
}
