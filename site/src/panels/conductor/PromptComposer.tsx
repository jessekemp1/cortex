import { useState } from 'react'
import { Card, SectionHeader } from '@/design-system/components'
import { cn } from '@/utils/cn'
import { useConductorStore } from '@/stores/conductorStore'
import type { PromptTemplate, ComposedPrompt, IntentLevel } from '@/types/conductor'

interface PromptComposerProps {
  templates: PromptTemplate[]
  composedPrompt: ComposedPrompt | null
  isComposing: boolean
  onCompose: (intent: string, projectId: string, intentLevel: IntentLevel, includeContext: boolean) => void
  projects: { id: string; name: string; icon: string }[]
}

export function PromptComposer({ templates, composedPrompt, isComposing, onCompose, projects }: PromptComposerProps) {
  const {
    selectedProject, setSelectedProject,
    intentLevel, setIntentLevel,
    userIntent, setUserIntent,
    includeContext, setIncludeContext,
    selectedTemplate, setSelectedTemplate,
  } = useConductorStore()

  const [copied, setCopied] = useState(false)

  const handleTemplateSelect = (template: PromptTemplate) => {
    setSelectedTemplate(template.id)
    setIntentLevel(template.intent_level)
    if (!userIntent) {
      setUserIntent(template.template.replace('{intent}', ''))
    }
  }

  const handleCompose = () => {
    if (!userIntent.trim() || !selectedProject) return

    let finalIntent = userIntent
    if (selectedTemplate) {
      const tmpl = templates.find(t => t.id === selectedTemplate)
      if (tmpl) {
        finalIntent = tmpl.template.replace('{intent}', userIntent)
      }
    }

    onCompose(finalIntent, selectedProject, intentLevel, includeContext)
  }

  const handleCopy = async () => {
    if (!composedPrompt) return
    try {
      await navigator.clipboard.writeText(composedPrompt.prompt)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
      const textarea = document.createElement('textarea')
      textarea.value = composedPrompt.prompt
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Template Quick-Select */}
      <div>
        <SectionHeader title="Quick Templates" count={templates.length} />
        <div className="grid grid-cols-3 lg:grid-cols-6 gap-2">
          {templates.map((tmpl) => (
            <button
              key={tmpl.id}
              onClick={() => handleTemplateSelect(tmpl)}
              className={cn(
                'flex flex-col items-center gap-1 p-3 rounded-panel border transition-all',
                selectedTemplate === tmpl.id
                  ? 'border-cortex-cyan bg-cortex-cyan-glow'
                  : 'border-cortex-border bg-cortex-elevated hover:border-cortex-cyan/50'
              )}
            >
              <span className="text-xl">{tmpl.icon}</span>
              <span className="text-[10px] font-display tracking-wider text-cortex-text-secondary">
                {tmpl.label.toUpperCase()}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Composer Form */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Input */}
        <div className="space-y-4">
          <div>
            <label className="text-xs font-data text-cortex-text-muted tracking-wider mb-2 block">
              PROJECT
            </label>
            <div className="flex flex-wrap gap-2">
              {projects.map((proj) => (
                <button
                  key={proj.id}
                  onClick={() => setSelectedProject(proj.id)}
                  className={cn(
                    'px-3 py-1.5 text-xs font-data tracking-wider rounded border transition-colors',
                    selectedProject === proj.id
                      ? 'border-cortex-cyan bg-cortex-cyan-muted text-cortex-cyan'
                      : 'border-cortex-border text-cortex-text-muted hover:border-cortex-cyan/50'
                  )}
                >
                  {proj.icon} {proj.name.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-data text-cortex-text-muted tracking-wider mb-2 block">
              INTENT
            </label>
            <textarea
              value={userIntent}
              onChange={(e) => setUserIntent(e.target.value)}
              placeholder="Describe what you want to accomplish..."
              rows={4}
              className="w-full bg-cortex-bg border border-cortex-border rounded-panel p-3 text-sm text-cortex-text-primary placeholder-cortex-text-muted font-mono focus:outline-none focus:border-cortex-cyan resize-none scrollbar-thin"
            />
          </div>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={includeContext}
                onChange={(e) => setIncludeContext(e.target.checked)}
                className="accent-cyan-500"
              />
              <span className="text-xs font-data text-cortex-text-secondary">Include project context</span>
            </label>

            <select
              value={intentLevel}
              onChange={(e) => setIntentLevel(e.target.value as IntentLevel)}
              className="bg-cortex-elevated border border-cortex-border rounded px-2 py-1 text-xs font-data text-cortex-text-primary focus:outline-none focus:border-cortex-cyan"
            >
              <option value="advisory">Advisory</option>
              <option value="collaborative">Collaborative</option>
              <option value="autonomous">Autonomous</option>
              <option value="supervisory">Supervisory</option>
            </select>
          </div>

          <button
            onClick={handleCompose}
            disabled={!userIntent.trim() || !selectedProject || isComposing}
            className={cn(
              'w-full px-4 py-3 font-display text-sm tracking-[0.15em] rounded-panel transition-colors',
              userIntent.trim() && selectedProject && !isComposing
                ? 'bg-cortex-cyan text-cortex-bg hover:bg-cortex-cyan/80'
                : 'bg-cortex-elevated text-cortex-text-muted cursor-not-allowed'
            )}
          >
            {isComposing ? 'COMPOSING...' : 'COMPOSE PROMPT'}
          </button>
        </div>

        {/* Right: Output */}
        <div>
          <label className="text-xs font-data text-cortex-text-muted tracking-wider mb-2 block">
            COMPOSED PROMPT
          </label>
          <Card variant="elevated" padding="none" className="relative">
            {composedPrompt ? (
              <>
                <pre className="p-4 text-xs text-cortex-text-primary font-mono whitespace-pre-wrap max-h-[400px] overflow-y-auto scrollbar-thin">
                  {composedPrompt.prompt}
                </pre>
                <div className="flex items-center justify-between p-3 border-t border-cortex-border">
                  <span className="text-[10px] font-data text-cortex-text-muted">
                    ~{composedPrompt.token_estimate} tokens · {composedPrompt.intent_level.toUpperCase()}
                  </span>
                  <button
                    onClick={handleCopy}
                    className="px-3 py-1 text-xs font-data tracking-wider bg-cortex-cyan-muted text-cortex-cyan rounded hover:bg-cortex-cyan/20 transition-colors"
                  >
                    {copied ? '✓ COPIED' : 'COPY'}
                  </button>
                </div>
              </>
            ) : (
              <div className="flex items-center justify-center h-64 text-cortex-text-muted">
                <div className="text-center">
                  <span className="text-3xl block mb-2">◇</span>
                  <span className="text-xs font-data tracking-wider">
                    SELECT A TEMPLATE OR WRITE YOUR INTENT
                  </span>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
