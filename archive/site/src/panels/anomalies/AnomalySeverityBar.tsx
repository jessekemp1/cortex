import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

interface AnomalySeverityBarProps {
  bySeverity: Record<string, number>
}

const severityColors: Record<string, string> = {
  CRITICAL: '#EF4444',
  WARNING: '#F59E0B',
  INFO: '#3B82F6',
}

export function AnomalySeverityBar({ bySeverity }: AnomalySeverityBarProps) {
  const data = Object.entries(bySeverity).map(([severity, count]) => ({
    severity,
    count,
  }))

  if (data.length === 0) return null

  return (
    <div className="h-16">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 60, right: 10, top: 0, bottom: 0 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="severity"
            tick={{ fill: '#9CA3AF', fontSize: 10, fontFamily: 'Share Tech Mono' }}
            width={55}
            axisLine={false}
            tickLine={false}
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
          <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={12}>
            {data.map((entry) => (
              <Cell key={entry.severity} fill={severityColors[entry.severity] ?? '#6B7280'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
