import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

interface CostSavingsChartProps {
  savings: number
  batchCost: number
  realTimeCost?: number
}

export function CostSavingsChart({ savings, batchCost }: CostSavingsChartProps) {
  // Generate mock 7-day trend data from the aggregate metrics
  const days = 7
  const dailySaving = savings / days
  const data = Array.from({ length: days }, (_, i) => ({
    day: `Day ${i + 1}`,
    savings: Math.round(dailySaving * (i + 1) * 100) / 100,
    batch: Math.round((batchCost / days) * (i + 1) * 100) / 100,
  }))

  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ left: 10, right: 10, top: 5, bottom: 0 }}>
          <defs>
            <linearGradient id="cyanGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#2A2D3A" />
          <XAxis
            dataKey="day"
            tick={{ fill: '#6B7280', fontSize: 10, fontFamily: 'Share Tech Mono' }}
            axisLine={{ stroke: '#2A2D3A' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#6B7280', fontSize: 10, fontFamily: 'Share Tech Mono' }}
            axisLine={{ stroke: '#2A2D3A' }}
            tickLine={false}
            tickFormatter={(v: number) => `$${v}`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1A1D27',
              border: '1px solid #2A2D3A',
              borderRadius: '6px',
              fontFamily: 'Share Tech Mono',
              fontSize: '12px',
            }}
          />
          <Area
            type="monotone"
            dataKey="savings"
            stroke="#06b6d4"
            fill="url(#cyanGrad)"
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
