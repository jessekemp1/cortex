// Conductor — Human-AI Collaboration Cockpit Types

export type IntentLevel = 'advisory' | 'collaborative' | 'autonomous' | 'supervisory'

export interface ConductorProject {
  id: string
  name: string
  icon: string
  last_commit: string
  last_commit_msg: string
  uncommitted_files: number
  test_cmd: string
}

export interface NextSession {
  project: string
  content: string
  age_hours?: number
}

export interface ConductorAlert {
  severity: string
  message: string
  type: string
}

export interface ConductorRecommendation {
  action: string
  priority: string
  type: string
}

export interface ConductorStartup {
  timestamp: string
  projects: ConductorProject[]
  git: {
    branch: string
    changed_files: number
  }
  next_session: NextSession | null
  alerts: ConductorAlert[]
  recommendations: ConductorRecommendation[]
  memory_snapshot: string | null
}

export interface PromptTemplate {
  id: string
  label: string
  icon: string
  template: string
  intent_level: IntentLevel
}

export interface ComposedPrompt {
  prompt: string
  project: string
  intent_level: IntentLevel
  token_estimate: number
}
