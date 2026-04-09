import { useState } from 'react'
import { Card } from '@/design-system/components'
import { SectionHeader } from '@/design-system/components'
import { cn } from '@/utils/cn'
import { useConductorStore } from '@/stores/conductorStore'
import type { ConductorStartup, IntentLevel } from '@/types/conductor'

const INTENT_LEVELS: { id: IntentLevel; label: string; icon: string; desc: string; color: string }[] = [
  { id: 'advisory', label: 'ADVISORY', icon: '🔍', desc: 'Research & recommend. No file changes.', color: 'text-cortex-processing' },
  { id: 'collaborative', label: 'COLLABORATIVE', icon: '🤝', desc: 'Propose, approve, execute.', color: 'text-cortex-cyan' },
  { id: 'autonomous', label: 'AUTONOMOUS', icon: '⚡', desc: 'Execute end-to-end. Report results.', color: 'text-cortex-nominal' },
  { id: 'supervisory', label: 'SUPERVISORY', icon: '🎯', desc: 'Orchestrate parallel sub-agents.', color: 'text-cortex-ai-suggestion' },
]

interface StartupWizardProps {
  data: ConductorStartup | undefined
  isLoading: boolean
  onLaunch: (projectId: string, intentLevel: IntentLevel) => void
}

export function StartupWizard({ data, isLoading, onLaunch }: StartupWizardProps) {
  const {
    selectedProject, setSelectedProject,
    intentLevel, setIntentLevel,
    wizardStep, setWizardStep,
  } = useConductorStore()

  const [copied, setCopied] = useState(false)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-cortex-cyan border-t-transparent rounded-full animate-spin" />
          <span className="font-data text-xs text-cortex-text-muted tracking-wider">LOADING STARTUP INTELLIGENCE</span>
        </div>
      </div>
    )
  }

  if (!data) return null

  const selectedProj = data.projects.find(p => p.id === selectedProject)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Alerts Banner */}
      {data.alerts.length > 0 && (
        <div className="space-y-2">
          {data.alerts.map((alert, i) => (
            <div
              key={i}
              className={cn(
                'flex items-center gap-3 px-4 py-2 rounded-panel border',
                alert.severity === 'HIGH'
                  ? 'bg-cortex-critical-muted/20 border-cortex-critical text-cortex-critical'
                  : 'bg-cortex-warning-muted/20 border-cortex-warning text-cortex-warning'
              )}
            >
              <span className="font-data text-xs tracking-wider flex-1">{alert.message}</span>
              <span className="text-[10px] font-display tracking-wider opacity-60">{alert.type}</span>
            </div>
          ))}
        </div>
      )}

      {/* Step 1: Select Project */}
      {wizardStep === 0 && (
        <div>
          <SectionHeader title="Select Project" count={data.projects.length} />
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            {data.projects.map((proj) => (
              <button
                key={proj.id}
                onClick={() => {
                  setSelectedProject(proj.id)
                  setWizardStep(1)
                }}
                className={cn(
                  'text-left bg-cortex-elevated border rounded-panel p-4 transition-all hover:border-cortex-cyan group',
                  selectedProject === proj.id
                    ? 'border-cortex-cyan bg-cortex-cyan-glow'
                    : 'border-cortex-border'
                )}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">{proj.icon}</span>
                  <span className="font-data text-xs tracking-wider text-cortex-text-primary group-hover:text-cortex-cyan">
                    {proj.name.toUpperCase()}
                  </span>
                </div>
                <div className="space-y-1">
                  {proj.last_commit_msg && (
                    <p className="text-xs text-cortex-text-muted truncate">
                      <span className="text-cortex-text-secondary font-data">{proj.last_commit}</span>{' '}
                      {proj.last_commit_msg}
                    </p>
                  )}
                  {proj.uncommitted_files > 0 && (
                    <p className="text-xs text-cortex-warning font-data">
                      {proj.uncommitted_files} uncommitted
                    </p>
                  )}
                </div>
              </button>
            ))}
          </div>

          {/* Next Session Preview */}
          {data.next_session && (
            <div className="mt-4">
              <SectionHeader title="Continue Previous Session" />
              <Card variant="accent" padding="md">
                <div className="flex items-center gap-2 mb-2">
                  <span className="px-2 py-0.5 text-[10px] font-display tracking-wider rounded bg-cortex-cyan-muted text-cortex-cyan">
                    {data.next_session.project.toUpperCase()}
                  </span>
                  {data.next_session.age_hours !== undefined && (
                    <span className="text-xs font-data text-cortex-text-muted">
                      {data.next_session.age_hours < 1
                        ? 'just now'
                        : `${Math.round(data.next_session.age_hours)}h ago`}
                    </span>
                  )}
                </div>
                <pre className="text-xs text-cortex-text-secondary font-mono whitespace-pre-wrap max-h-32 overflow-y-auto scrollbar-thin">
                  {data.next_session.content.slice(0, 500)}
                </pre>
                <button
                  onClick={() => {
                    setSelectedProject(data.next_session!.project)
                    setWizardStep(1)
                  }}
                  className="mt-3 px-4 py-1.5 text-xs font-data tracking-wider bg-cortex-cyan-muted text-cortex-cyan rounded hover:bg-cortex-cyan/20 transition-colors"
                >
                  CONTINUE SESSION →
                </button>
              </Card>
            </div>
          )}

          {/* Recommendations */}
          {data.recommendations.length > 0 && (
            <div className="mt-4">
              <SectionHeader title="Recommended Next Action" />
              {data.recommendations.map((rec, i) => (
                <Card key={i} variant="elevated" padding="md">
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      'px-1.5 py-0.5 text-[10px] font-display tracking-wider rounded',
                      rec.priority === 'HIGH'
                        ? 'bg-cortex-warning-muted text-cortex-warning'
                        : 'bg-cortex-processing-muted text-cortex-processing'
                    )}>
                      {rec.priority}
                    </span>
                    <span className="text-sm text-cortex-text-primary">{rec.action}</span>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Step 2: Select Intent Level */}
      {wizardStep === 1 && selectedProj && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={() => setWizardStep(0)}
              className="text-xs font-data text-cortex-text-muted hover:text-cortex-cyan transition-colors"
            >
              ← BACK
            </button>
            <span className="text-cortex-text-muted">|</span>
            <span className="text-sm font-data text-cortex-cyan">
              {selectedProj.icon} {selectedProj.name.toUpperCase()}
            </span>
          </div>

          <SectionHeader title="Set Intent Level" />
          <div className="grid grid-cols-2 gap-3">
            {INTENT_LEVELS.map((level) => (
              <button
                key={level.id}
                onClick={() => {
                  setIntentLevel(level.id)
                  setWizardStep(2)
                }}
                className={cn(
                  'text-left bg-cortex-elevated border rounded-panel p-4 transition-all hover:border-cortex-cyan',
                  intentLevel === level.id
                    ? 'border-cortex-cyan bg-cortex-cyan-glow'
                    : 'border-cortex-border'
                )}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-lg">{level.icon}</span>
                  <span className={cn('font-display text-xs tracking-[0.15em]', level.color)}>
                    {level.label}
                  </span>
                </div>
                <p className="text-xs text-cortex-text-muted">{level.desc}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 3: Review & Launch */}
      {wizardStep === 2 && selectedProj && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={() => setWizardStep(1)}
              className="text-xs font-data text-cortex-text-muted hover:text-cortex-cyan transition-colors"
            >
              ← BACK
            </button>
            <span className="text-cortex-text-muted">|</span>
            <span className="text-sm font-data text-cortex-cyan">
              {selectedProj.icon} {selectedProj.name.toUpperCase()}
            </span>
            <span className="text-cortex-text-muted">|</span>
            <span className="text-sm font-data text-cortex-ai-suggestion">
              {intentLevel.toUpperCase()}
            </span>
          </div>

          <SectionHeader title="Session Summary" />

          <Card variant="accent" padding="lg">
            <div className="space-y-4">
              <div>
                <span className="text-xs font-data text-cortex-text-muted tracking-wider">PROJECT</span>
                <p className="text-sm text-cortex-text-primary mt-1">{selectedProj.name}</p>
              </div>
              <div>
                <span className="text-xs font-data text-cortex-text-muted tracking-wider">INTENT LEVEL</span>
                <p className="text-sm text-cortex-text-primary mt-1">
                  {INTENT_LEVELS.find(l => l.id === intentLevel)?.icon}{' '}
                  {intentLevel.toUpperCase()} — {INTENT_LEVELS.find(l => l.id === intentLevel)?.desc}
                </p>
              </div>
              <div>
                <span className="text-xs font-data text-cortex-text-muted tracking-wider">GIT STATUS</span>
                <p className="text-sm text-cortex-text-primary mt-1">
                  Branch: <span className="text-cortex-cyan font-data">{data.git.branch}</span>
                  {selectedProj.uncommitted_files > 0 && (
                    <span className="text-cortex-warning ml-3">
                      {selectedProj.uncommitted_files} uncommitted changes
                    </span>
                  )}
                </p>
              </div>
              {data.next_session && data.next_session.project === selectedProject && (
                <div>
                  <span className="text-xs font-data text-cortex-text-muted tracking-wider">PREVIOUS SESSION</span>
                  <pre className="text-xs text-cortex-text-secondary font-mono mt-1 whitespace-pre-wrap max-h-24 overflow-y-auto scrollbar-thin">
                    {data.next_session.content.slice(0, 300)}
                  </pre>
                </div>
              )}
            </div>

            <div className="flex gap-3 mt-6 pt-4 border-t border-cortex-border">
              <button
                onClick={() => {
                  onLaunch(selectedProject!, intentLevel)
                  setCopied(true)
                  setTimeout(() => setCopied(false), 2000)
                }}
                className="flex-1 px-6 py-3 font-display text-sm tracking-[0.15em] bg-cortex-cyan text-cortex-bg rounded-panel hover:bg-cortex-cyan/80 transition-colors"
              >
                {copied ? '✓ COPIED TO CLIPBOARD' : 'GENERATE & COPY PROMPT'}
              </button>
              <button
                onClick={() => {
                  setWizardStep(0)
                  setSelectedProject(null)
                }}
                className="px-4 py-3 font-data text-xs tracking-wider text-cortex-text-muted hover:text-cortex-text-primary bg-cortex-elevated border border-cortex-border rounded-panel transition-colors"
              >
                RESET
              </button>
            </div>
          </Card>
        </div>
      )}

      {/* Global Status Footer */}
      <div className="flex items-center justify-between pt-4 border-t border-cortex-border">
        <span className="text-xs font-data text-cortex-text-muted">
          {data.git.branch} · {data.git.changed_files} changes · {data.projects.length} projects
        </span>
        <span className="text-xs font-data text-cortex-text-muted">
          {new Date(data.timestamp).toLocaleTimeString()}
        </span>
      </div>
    </div>
  )
}
