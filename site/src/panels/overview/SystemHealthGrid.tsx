import { useProjectsQuery } from '@/api/hooks'
import { ProjectStatusCard } from './ProjectStatusCard'
import type { ProjectStatus } from '@/types/cortex'

const fallbackProjects: ProjectStatus[] = [
  { name: 'VortexV2', status: 'healthy', health_score: 95, last_activity: '', key_metric: 'Models', key_metric_value: '6/6 PASS' },
  { name: 'VortexV3', status: 'healthy', health_score: 100, last_activity: '', key_metric: 'Tests', key_metric_value: '50/50' },
  { name: 'Cortex', status: 'healthy', health_score: 90, last_activity: '', key_metric: 'Version', key_metric_value: 'v1.0.0' },
  { name: 'Alpha Arena', status: 'warning', health_score: 60, last_activity: '', key_metric: 'Phase', key_metric_value: 'Planning' },
]

export function SystemHealthGrid() {
  const { data: projects } = useProjectsQuery()
  const displayProjects = projects ?? fallbackProjects

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
      {displayProjects.map((project) => (
        <ProjectStatusCard key={project.name} project={project} />
      ))}
    </div>
  )
}
