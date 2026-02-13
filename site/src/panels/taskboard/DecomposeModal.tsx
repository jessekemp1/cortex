import { useState } from 'react'
import { Button } from '@/design-system/components/Button'
import { useDecomposeTaskMutation, useCreateTaskBoardTaskMutation } from '@/api/hooks'

interface DecomposeModalProps {
  onClose: () => void
}

const PROJECTS = ['VortexV2', 'VortexV3', 'Cortex', 'Winfield', 'Alpha Arena']

export function DecomposeModal({ onClose }: DecomposeModalProps) {
  const [description, setDescription] = useState('')
  const [project, setProject] = useState('VortexV2')
  const [context, setContext] = useState('')
  const decomposeMutation = useDecomposeTaskMutation()
  const createMutation = useCreateTaskBoardTaskMutation()
  const [saved, setSaved] = useState(false)

  const handleDecompose = () => {
    decomposeMutation.mutate({ description, project, context })
  }

  const handleSaveAll = () => {
    const result = decomposeMutation.data
    if (!result) return

    // Save parent task
    createMutation.mutate({
      title: result.parent_task.title,
      description: result.parent_task.description,
      project: result.parent_task.project,
      priority: result.parent_task.priority,
      tags: result.parent_task.tags,
    })

    // Save subtasks
    for (const sub of result.subtasks) {
      createMutation.mutate({
        title: sub.title,
        description: sub.description,
        project: sub.project,
        priority: sub.priority,
        tags: sub.tags,
      })
    }

    setSaved(true)
    setTimeout(onClose, 1000)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-cortex-surface border border-cortex-border rounded-panel w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-cortex-border">
          <h3 className="font-display text-sm font-semibold tracking-[0.15em] uppercase text-cortex-text-primary">
            Decompose Spec
          </h3>
          <button
            onClick={onClose}
            className="text-cortex-text-muted hover:text-cortex-text-primary text-lg leading-none"
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div className="p-4 space-y-4">
          {/* Description */}
          <div>
            <label className="block text-[10px] font-data text-cortex-text-muted uppercase tracking-wider mb-1">
              Feature / Spec Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the feature or spec to decompose..."
              className="w-full h-24 px-3 py-2 bg-cortex-elevated border border-cortex-border rounded text-sm font-data text-cortex-text-primary placeholder:text-cortex-text-muted resize-none focus:outline-none focus:border-cortex-cyan"
            />
          </div>

          {/* Project selector */}
          <div>
            <label className="block text-[10px] font-data text-cortex-text-muted uppercase tracking-wider mb-1">
              Project
            </label>
            <div className="flex gap-2">
              {PROJECTS.map((p) => (
                <button
                  key={p}
                  onClick={() => setProject(p)}
                  className={`px-2 py-1 text-[10px] font-mono uppercase tracking-wider rounded border transition-colors ${
                    project === p
                      ? 'bg-cortex-elevated border-cortex-cyan text-cortex-cyan'
                      : 'bg-transparent border-cortex-border text-cortex-text-muted hover:text-cortex-text-secondary'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* Context */}
          <div>
            <label className="block text-[10px] font-data text-cortex-text-muted uppercase tracking-wider mb-1">
              Additional Context (optional)
            </label>
            <input
              type="text"
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="e.g. depends on EMOS being ready"
              className="w-full px-3 py-2 bg-cortex-elevated border border-cortex-border rounded text-sm font-data text-cortex-text-primary placeholder:text-cortex-text-muted focus:outline-none focus:border-cortex-cyan"
            />
          </div>

          {/* Decompose button */}
          {!decomposeMutation.data && (
            <Button
              variant="primary"
              size="sm"
              onClick={handleDecompose}
              disabled={!description.trim() || decomposeMutation.isPending}
            >
              {decomposeMutation.isPending ? 'DECOMPOSING...' : 'DECOMPOSE'}
            </Button>
          )}

          {/* Results */}
          {decomposeMutation.data && (
            <div className="space-y-2">
              <div className="text-[10px] font-display uppercase tracking-wider text-cortex-text-secondary">
                Generated Tasks
              </div>
              <div className="space-y-1.5">
                <div className="p-2 bg-cortex-elevated rounded border border-cortex-cyan/30">
                  <span className="text-xs font-data text-cortex-cyan">PARENT:</span>{' '}
                  <span className="text-xs font-data text-cortex-text-primary">
                    {decomposeMutation.data.parent_task.title}
                  </span>
                </div>
                {decomposeMutation.data.subtasks.map((sub, i) => (
                  <div key={i} className="p-2 bg-cortex-elevated rounded border border-cortex-border">
                    <span className="text-[10px] font-mono text-cortex-text-muted">
                      {sub.priority}
                    </span>{' '}
                    <span className="text-xs font-data text-cortex-text-primary">{sub.title}</span>
                  </div>
                ))}
              </div>

              <div className="flex gap-2">
                <Button variant="primary" size="sm" onClick={handleSaveAll} disabled={saved}>
                  {saved ? 'SAVED' : 'SAVE ALL TO BOARD'}
                </Button>
                <Button variant="ghost" size="sm" onClick={onClose}>
                  CANCEL
                </Button>
              </div>
            </div>
          )}

          {decomposeMutation.error && (
            <div className="text-cortex-critical text-xs font-data">
              Decomposition failed: {decomposeMutation.error.message}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
