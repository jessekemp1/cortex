# Cortex Batch API Integration Layer

Complete API integration for Cortex Batch Command Center.

## Quick Start

```typescript
import { useBatchesQuery, useQueueQuery, useMetricsQuery } from '@/api'

function MyComponent() {
  const { data: batches } = useBatchesQuery()
  const { data: queue } = useQueueQuery()
  const { data: metrics } = useMetricsQuery(7)

  return (
    <div>
      <div>Active Batches: {batches?.length ?? 0}</div>
      <div>Queued Tasks: {queue?.length ?? 0}</div>
      <div>7-Day Savings: ${metrics?.cost_estimate.savings ?? 0}</div>
    </div>
  )
}
```

## Files

- **`types.ts`** - API response types (BatchStatus, PendingTask, UsageMetrics, etc.)
- **`client.ts`** - Axios client with error handling and interceptors
- **`hooks.ts`** - React Query hooks with automatic polling
- **`index.ts`** - Central export for easy imports

## Features

✅ Full TypeScript support
✅ Automatic polling with configurable intervals
✅ Request/response interceptors
✅ Error handling with friendly messages
✅ Mutations with automatic cache invalidation
✅ Prefetching utilities

## Polling Intervals

| Hook | Interval | Notes |
|------|----------|-------|
| `useHealthQuery()` | 60s | System health |
| `useBatchesQuery()` | 30s | Batch list |
| `useBatchStatusQuery()` | 5s | Stops when ended |
| `useQueueQuery()` | 10s | Queue status |
| `useMetricsQuery()` | 5m | Cost/usage metrics |

## Environment Variables

```bash
# .env
VITE_CORTEX_API_URL=http://localhost:8765  # Default
```

## See Also

- `/Users/jesse.kemp/Dev/cortex/site/API_LAYER_README.md` - Full documentation
- `../types/batch.ts` - Enriched domain types
- `../utils/calculations.ts` - Calculation utilities
