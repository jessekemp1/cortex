export type SessionStatus = 'ACTIVE' | 'WAITING' | 'IDLE' | 'STALE'

export interface Session {
  id: string
  project: string
  status: SessionStatus
  git_branch: string
  last_event_type: string
  last_event_age_seconds: number
  started_at: string
  last_activity: string
  event_count: number
  model: string
  cwd: string
}

export interface SessionsResponse {
  sessions: Session[]
  total: number
  active_count: number
}

export const SESSION_STATUS_COLORS: Record<SessionStatus, string> = {
  ACTIVE: '#10B981',   // nominal green
  WAITING: '#F59E0B',  // amber — needs user attention
  IDLE: '#6B7280',     // muted gray
  STALE: '#374151',    // dark gray
}

export const SESSION_STATUS_PULSE: Record<SessionStatus, boolean> = {
  ACTIVE: true,
  WAITING: true,
  IDLE: false,
  STALE: false,
}
