# Cortex Batch Command Center - API Layer

## Overview

Task 2 implementation: Complete API integration layer for communicating with Cortex batch services.

## Files Created

### API Layer (`src/api/`)

#### `types.ts` (1.6KB)
Core API response types matching Cortex backend:
- `BatchStatus` - Batch job status from Anthropic API
- `PendingTask` - Local queue task definition
- `UsageMetrics` - Cost/usage statistics
- `HealthResponse` - System health check
- `APIError` - Error response structure

#### `client.ts` (4.0KB)
Axios-based API client with error handling:
- Base URL: `http://localhost:8765` (configurable via `VITE_CORTEX_API_URL`)
- **Health API**: `getHealth()`
- **Batch API**: `listBatches()`, `getBatchStatus()`, `cancelBatch()`
- **Queue API**: `getQueue()`, `addTask()`, `updateTaskPriority()`, `deleteTask()`
- **Metrics API**: `getMetrics(days)`
- Request/response interceptors with friendly error messages

#### `hooks.ts` (4.9KB)
React Query hooks with automatic polling:
- `useHealthQuery()` - Poll every 60s
- `useBatchesQuery()` - Poll every 30s
- `useBatchStatusQuery(id, enabled)` - Poll every 5s (stops when batch ends)
- `useQueueQuery()` - Poll every 10s
- `useMetricsQuery(days)` - Poll every 5m
- Mutations: `useAddTaskMutation()`, `useUpdateTaskPriorityMutation()`, `useDeleteTaskMutation()`, `useCancelBatchMutation()`

#### `index.ts` (0.6KB)
Central export for all API modules

### Domain Types (`src/types/`)

#### `batch.ts` (1.6KB)
Enriched types for UI:
- `EnrichedBatchStatus` - Batch with computed metrics (progress %, error rate, elapsed time, req/sec)
- `EnrichedPendingTask` - Task with AI recommendations and queue position
- `AIRecommendation` - AI-generated scheduling suggestions
- `DashboardSummary` - Summary statistics
- `QueueHealth` - Queue health metrics

### Utilities (`src/utils/`)

#### `calculations.ts` (8.9KB)
Business logic for metrics and recommendations:

**Batch Calculations:**
- `calculateProgress(batch)` - Progress percentage (0-100)
- `calculateErrorRate(batch)` - Error rate percentage
- `calculateElapsedSeconds(batch)` - Time since batch creation
- `calculateRequestsPerSecond(batch)` - Processing rate
- `enrichBatchStatus(batch)` - Add all computed fields

**Task Calculations:**
- `estimateDuration(tokens)` - Duration in minutes (~100 tokens/sec)
- `calculateQueuePosition(task, allTasks)` - Position based on priority + timestamp
- `generateRecommendation(task, allTasks)` - AI suggestions (mock implementation)
- `enrichPendingTask(task, allTasks)` - Add computed fields + AI rec

**Formatters:**
- `formatDuration(seconds)` - "2h 15m", "45s"
- `formatTokens(tokens)` - "1.2K", "3.5M"
- `calculateSavingsPercentage(realTime, batch)` - Savings %

#### `index.ts` (0.7KB)
Central export for all utilities

### Config

#### `vite-env.d.ts` (163B)
TypeScript environment types:
- `VITE_CORTEX_API_URL` - API base URL override

## Usage Examples

### Basic Query
```typescript
import { useBatchesQuery, useQueueQuery } from '@/api'

function Dashboard() {
  const { data: batches, isLoading } = useBatchesQuery()
  const { data: queue } = useQueueQuery()

  return <div>{batches?.length} active batches</div>
}
```

### Specific Batch Monitoring
```typescript
import { useBatchStatusQuery } from '@/api'
import { enrichBatchStatus } from '@/utils'

function BatchMonitor({ batchId }: { batchId: string }) {
  const { data } = useBatchStatusQuery(batchId, true)

  if (!data) return null

  const enriched = enrichBatchStatus(data)
  return (
    <div>
      <div>Progress: {enriched.progress_percentage}%</div>
      <div>Error Rate: {enriched.error_rate}%</div>
      <div>Speed: {enriched.requests_per_second} req/s</div>
    </div>
  )
}
```

### Queue with AI Recommendations
```typescript
import { useQueueQuery } from '@/api'
import { enrichPendingTask } from '@/utils'

function QueueView() {
  const { data: tasks } = useQueueQuery()

  const enrichedTasks = tasks?.map(task =>
    enrichPendingTask(task, tasks)
  )

  return (
    <div>
      {enrichedTasks?.map(task => (
        <div key={task.id}>
          <div>Position: #{task.position_in_queue}</div>
          <div>Duration: ~{task.estimated_duration_minutes}m</div>
          {task.ai_recommendation && (
            <div>
              Suggestion: {task.ai_recommendation.suggestion}
              ({(task.ai_recommendation.confidence * 100).toFixed(0)}% confidence)
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
```

### Mutations
```typescript
import { useAddTaskMutation, useUpdateTaskPriorityMutation } from '@/api'

function QueueActions() {
  const addTask = useAddTaskMutation()
  const updatePriority = useUpdateTaskPriorityMutation()

  const handleAdd = () => {
    addTask.mutate({
      title: 'New task',
      description: 'Do something',
      priority: 'NORMAL',
      estimated_tokens: 5000,
    })
  }

  const handleUpgrade = (taskId: string) => {
    updatePriority.mutate({ taskId, priority: 'HIGH' })
  }

  return (
    <div>
      <button onClick={handleAdd}>Add Task</button>
    </div>
  )
}
```

## API Endpoints

All endpoints are relative to `http://localhost:8765` (Cortex Bridge):

- `GET /health` - Health check
- `GET /batches?limit=20` - List batches
- `GET /batches/:id` - Batch details
- `POST /batches/:id/cancel` - Cancel batch
- `GET /queue` - Get queue
- `POST /queue` - Add task
- `PATCH /queue/:id` - Update task
- `DELETE /queue/:id` - Delete task
- `GET /metrics?days=7` - Usage metrics

## Polling Intervals

- Health: 60s
- Batch list: 30s
- Specific batch: 5s (stops when ended)
- Queue: 10s
- Metrics: 5m

## AI Recommendations

Mock implementation uses heuristics:
- **run_now**: CRITICAL priority, deadline < 2h, blocking other tasks
- **reprioritize_up**: Deadline approaching but LOW priority
- **defer**: submit_after constraint, LOW priority with no deadline
- **none**: Appropriately scheduled

Future: Replace with actual Cortex intelligence API.

## Type Safety

All API responses are fully typed. TypeScript will catch:
- Missing required fields
- Incorrect priority values
- Invalid status transitions
- Type mismatches

Run `npm run type-check` to verify.

## Testing

Type check: `npm run type-check` ✅ PASSING

Integration testing framework not yet configured. Test files were excluded.

## Next Steps

1. Create React components to consume these hooks (Task 3)
2. Build dashboard layout (Task 4)
3. Add charts for visualizations (Task 5)
4. Implement backend Cortex Bridge endpoints
5. Replace mock AI recommendations with real Cortex intelligence

## Reference Files

Patterns inspired by:
- `~/Dev/Vortex/VortexV3/src/api/client.ts`
- `~/Dev/Vortex/VortexV3/src/api/hooks.ts`
- `~/Dev/cortex/batch/batch_api_client.py`
- `~/Dev/cortex/batch/dashboard.py`

## File Locations

All files in `~/Dev/cortex/site/src/`:
- `api/types.ts`
- `api/client.ts`
- `api/hooks.ts`
- `api/index.ts`
- `types/batch.ts`
- `utils/calculations.ts`
- `utils/index.ts`
- `vite-env.d.ts`
