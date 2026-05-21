import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { SectionHeader } from '@/design-system/components'
import { cn } from '@/utils/cn'
import { cortexApi } from '@/api/client'
import { StartupWizard } from './StartupWizard'
import { SessionMonitor } from './SessionMonitor'
import { PromptComposer } from './PromptComposer'
import type { ConductorStartup, PromptTemplate, ComposedPrompt, IntentLevel } from '@/types/conductor'

type TabId = 'startup' | 'monitor' | 'composer'

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'startup', label: 'STARTUP', icon: '▶' },
  { id: 'monitor', label: 'MONITOR', icon: '◎' },
  { id: 'composer', label: 'COMPOSE', icon: '◇' },
]

export default function ConductorPanel() {
  const [activeTab, setActiveTab] = useState<TabId>('startup')

  // Fetch startup data
  const { data: startupData, isLoading: startupLoading } = useQuery<ConductorStartup>({
    queryKey: ['conductor', 'startup'],
    queryFn: async () => {
      const res = await cortexApi.get('/conductor/startup')
      return res.data
    },
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 60,
  })

  // Fetch templates
  const { data: templatesData } = useQuery<{ templates: PromptTemplate[] }>({
    queryKey: ['conductor', 'templates'],
    queryFn: async () => {
      const res = await cortexApi.get('/conductor/templates')
      return res.data
    },
    staleTime: 1000 * 60 * 10,
  })

  // Compose prompt mutation
  interface ComposeParams {
    intent: string
    project_id: string
    intent_level: string
    include_context: boolean
  }

  const composeMutation = useMutation<ComposedPrompt, Error, ComposeParams>({
    mutationFn: async (params) => {
      const res = await cortexApi.post('/conductor/compose', params)
      return res.data
    },
  })

  const handleLaunch = async (projectId: string, intentLevel: IntentLevel) => {
    const result = await composeMutation.mutateAsync({
      intent: `Starting new session. Continue from .next_session if available.`,
      project_id: projectId,
      intent_level: intentLevel,
      include_context: true,
    })

    // Copy to clipboard
    try {
      await navigator.clipboard.writeText(result.prompt)
    } catch {
      const textarea = document.createElement('textarea')
      textarea.value = result.prompt
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
  }

  const handleCompose = async (intent: string, projectId: string, intentLevel: IntentLevel, includeContext: boolean) => {
    await composeMutation.mutateAsync({
      intent,
      project_id: projectId,
      intent_level: intentLevel,
      include_context: includeContext,
    })
  }

  const projects = startupData?.projects.map(p => ({ id: p.id, name: p.name, icon: p.icon })) ?? []

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <SectionHeader title="Conductor" />
        <span className="text-xs font-data text-cortex-text-muted tracking-wider">
          HUMAN-AI COLLABORATION COCKPIT
        </span>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 bg-cortex-surface p-1 rounded-panel border border-cortex-border">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded transition-all',
              activeTab === tab.id
                ? 'bg-cortex-cyan-muted text-cortex-cyan'
                : 'text-cortex-text-muted hover:text-cortex-text-primary hover:bg-cortex-elevated'
            )}
          >
            <span className="text-sm">{tab.icon}</span>
            <span className="font-display text-[11px] tracking-[0.15em]">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'startup' && (
        <StartupWizard
          data={startupData}
          isLoading={startupLoading}
          onLaunch={handleLaunch}
        />
      )}

      {activeTab === 'monitor' && (
        <SessionMonitor
          data={startupData}
          isLoading={startupLoading}
        />
      )}

      {activeTab === 'composer' && (
        <PromptComposer
          templates={templatesData?.templates ?? []}
          composedPrompt={composeMutation.data ?? null}
          isComposing={composeMutation.isPending}
          onCompose={handleCompose}
          projects={projects}
        />
      )}
    </div>
  )
}
