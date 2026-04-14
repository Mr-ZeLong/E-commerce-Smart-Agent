import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { Task, TaskFilters, TaskStats } from '@/types'
import { apiFetch } from '@/lib/api'


interface SubmitDecisionPayload {
  audit_log_id: number
  action: 'APPROVE' | 'REJECT'
  comment: string
  admin_id?: string | number
}

interface TaskStatsResponse {
  risk_tasks: number
  confidence_tasks: number
  manual_tasks: number
  total: number
}

export function useTasks(filters: TaskFilters) {
  const queryClient = useQueryClient()

  const { data: tasks, isLoading } = useQuery<Task[]>({
    queryKey: ['admin', 'tasks', filters],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filters.riskLevel && filters.riskLevel !== 'ALL') {
        params.append('risk_level', filters.riskLevel)
      }
      const res = await apiFetch(`/admin/tasks?${params.toString()}`)
      if (!res.ok) {
        throw new Error('获取任务列表失败')
      }
      return res.json() as Promise<Task[]>
    },
  })

  const { mutateAsync: submitDecision, isPending: isSubmitting } = useMutation({
    mutationFn: async (payload: SubmitDecisionPayload) => {
      const res = await apiFetch(`/admin/resume/${payload.audit_log_id}`, {
        method: 'POST',
        body: JSON.stringify({
          action: payload.action,
          admin_comment: payload.comment,
        }),
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '提交决策失败')
      }
      return res.json() as Promise<unknown>
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'tasks'] })
      void queryClient.invalidateQueries({ queryKey: ['admin', 'taskStats'] })
    },
  })

  return {
    tasks: tasks ?? [],
    isLoading,
    submitDecision,
    isSubmitting,
  }
}

export function useTaskStats() {
  return useQuery<TaskStats>({
    queryKey: ['admin', 'taskStats'],
    queryFn: async () => {
      const res = await apiFetch('/admin/tasks-all')
      if (!res.ok) {
        throw new Error('获取统计失败')
      }
      const data = (await res.json()) as TaskStatsResponse
      return {
        pending: data.total,
        high_risk: data.risk_tasks,
      }
    },
  })
}
