# Cortex Batch Command Center

Military-themed command center dashboard for AI-powered batch orchestration and intelligence.

## Tech Stack

- **React 18** with TypeScript
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **Zustand** - State management
- **TanStack Query** - Data fetching
- **Axios** - HTTP client

## Design System

Military/tactical command center theme inspired by Anduril Lattice.

### Color Palette

- **Background**: Near-black hierarchy (`#05050A`, `#0F1117`, `#1A1D27`)
- **Status Colors**:
  - Nominal (Green): `#10B981` - Systems operational
  - Warning (Amber): `#F59E0B` - Attention required
  - Critical (Red): `#EF4444` - Critical alert
  - Processing (Blue): `#3B82F6` - Active operations
  - AI Suggestion (Purple): `#A855F7` - AI recommendations

### Components

All components located in `/src/design-system/components/`:

1. **Card** - Container with variants (default, elevated, outlined)
2. **Button** - Military styled with variants (primary, secondary, ghost, danger)
3. **StatusBadge** - Status indicator with pulse animation for active states
4. **ProgressRing** - SVG circular progress with percentage display
5. **MetricDisplay** - Large metric display with trend indicators
6. **PriorityBadge** - Priority levels (CRITICAL, HIGH, MEDIUM, LOW)

### Typography

- **Sans**: Inter - UI text
- **Mono**: JetBrains Mono - Data, metrics, labels

## Development

```bash
# Install dependencies
npm install

# Start dev server (http://localhost:5173)
npm run dev

# Type check
npm run type-check

# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
site/
├── src/
│   ├── layouts/
│   │   └── CommandCenterLayout.tsx    # Main 3-column layout
│   ├── panels/
│   │   ├── shared/
│   │   │   ├── StatusBar.tsx          # Top status bar
│   │   │   └── BottomActionBar.tsx    # Bottom action bar
│   │   ├── running/
│   │   │   ├── RunningPanel.tsx       # Active batches panel
│   │   │   └── ActiveBatchCard.tsx    # Batch card component
│   │   ├── pending/
│   │   │   ├── PendingQueuePanel.tsx  # Queued tasks panel
│   │   │   ├── PendingTaskCard.tsx    # Task card component
│   │   │   └── AIRecommendations.tsx  # AI suggestion component
│   │   └── completed/
│   │       ├── CompletedPanel.tsx     # History panel
│   │       └── CompletedJobCard.tsx   # Completed batch card
│   ├── design-system/
│   │   ├── components/                # Reusable UI components
│   │   │   ├── Button.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── MetricDisplay.tsx
│   │   │   ├── PriorityBadge.tsx
│   │   │   ├── ProgressRing.tsx
│   │   │   ├── StatusBadge.tsx
│   │   │   └── index.ts
│   │   └── tokens.ts                  # Design tokens
│   ├── api/
│   │   ├── client.ts                  # Axios instance
│   │   ├── hooks.ts                   # React Query hooks
│   │   └── types.ts                   # API types
│   ├── stores/
│   │   └── batchStore.ts              # Zustand state
│   ├── utils/
│   │   ├── cn.ts                      # Class name utility
│   │   ├── formatters.ts              # Format utilities
│   │   └── calculations.ts            # Metric calculations
│   ├── types/
│   │   └── batch.ts                   # Domain types
│   ├── App.tsx                        # Main app component
│   ├── main.tsx                       # Entry point
│   └── index.css                      # Global styles
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
└── index.html
```

## Dashboard Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           STATUS BAR                                │
│  [● NOMINAL]  [API: Connected]  [CORTEX COMMAND CENTER]  [UTC TIME] │
├──────────────────┬────────────────────────┬─────────────────────────┤
│                  │                        │                         │
│  RUNNING PANEL   │    PENDING PANEL       │   COMPLETED PANEL       │
│  (Left - 25%)    │    (Center - 50%)      │   (Right - 25%)         │
│                  │                        │                         │
│  - Active Ops    │  - Queued Tasks        │  - Historical Data      │
│  - Capacity      │  - AI Recommendations  │  - Success Rates        │
│  - Progress      │  - Queue Metrics       │  - Cost Savings         │
│                  │                        │                         │
├──────────────────┴────────────────────────┴─────────────────────────┤
│                        BOTTOM ACTION BAR                            │
│  [Submit New Batch]  [Refresh All]  [Settings]  Last updated: 5s   │
└─────────────────────────────────────────────────────────────────────┘
```

## Features

### StatusBar (Top)
- Real-time system health monitoring
- API connection status
- Live UTC clock (updates every second)
- Cost savings tracker

### Running Panel (Left)
- Active batch operations with real-time progress
- Capacity indicator (0/5 slots)
- Progress rings with percentage
- Error rates and processing speeds

### Pending Queue Panel (Center)
- Queued tasks awaiting submission
- AI-powered recommendations
- Priority badges (CRITICAL, HIGH, MEDIUM, LOW)
- Queue metrics and estimates

### Completed Panel (Right)
- Historical batch completion data
- Time filters: Today | 7 Days | 30 Days
- Success rate tracking
- Collapsible cards with detailed results

### BottomActionBar (Bottom)
- Quick actions: Submit, Refresh, Settings
- Last updated timestamp

## API Integration

The dashboard connects to the Cortex Bridge API (default: http://localhost:8765):

```
GET  /health            - System health check
GET  /batches           - List active/completed batches
GET  /batches/:id       - Get specific batch status
POST /batches/:id/cancel - Cancel a running batch
GET  /queue             - List pending tasks
POST /queue             - Add task to queue
PATCH /queue/:id        - Update task priority
DELETE /queue/:id       - Remove task from queue
GET  /metrics?days=N    - Get usage metrics
```

Set via environment variable:
```bash
VITE_CORTEX_API_URL=http://localhost:8765
```

## Design Principles

1. **Functional First** - No decorative elements, everything serves a purpose
2. **Status-Driven** - Color indicates system state
3. **High Contrast** - Dark backgrounds with bright status colors
4. **Monospace Data** - All metrics and data use JetBrains Mono
5. **Tactical Aesthetics** - Military command center inspiration
6. **Pulse Animations** - Active states show pulse to indicate processing
7. **Auto-refresh** - Queries refresh every 5 seconds for real-time updates
