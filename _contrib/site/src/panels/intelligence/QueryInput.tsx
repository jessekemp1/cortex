import { useState } from 'react'
import { cn } from '@/utils/cn'

interface QueryInputProps {
  onSubmit: (query: string) => void
  isLoading: boolean
}

export function QueryInput({ onSubmit, isLoading }: QueryInputProps) {
  const [text, setText] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (text.trim() && !isLoading) {
      onSubmit(text.trim())
      setText('')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Query Cortex intelligence..."
        className={cn(
          'flex-1 bg-cortex-elevated border border-cortex-border rounded-panel px-4 py-3',
          'font-data text-sm text-cortex-text-primary placeholder:text-cortex-text-muted',
          'focus:outline-none focus:border-cortex-cyan focus:ring-1 focus:ring-cortex-cyan/30',
          'transition-colors'
        )}
        disabled={isLoading}
      />
      <button
        type="submit"
        disabled={isLoading || !text.trim()}
        className={cn(
          'px-6 py-3 rounded-panel font-display text-xs font-semibold tracking-wider transition-colors',
          'bg-cortex-cyan-muted text-cortex-cyan border border-cortex-cyan/30',
          'hover:bg-cortex-cyan/20 disabled:opacity-40 disabled:cursor-not-allowed'
        )}
      >
        {isLoading ? 'QUERYING...' : 'QUERY'}
      </button>
    </form>
  )
}
