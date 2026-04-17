import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { Experiment, ExperimentCreatePayload, ExperimentResult } from '@/types'
import { apiFetch } from '@/lib/api'

export function useExperiments(status?: string) {
  const queryClient = useQueryClient()

  const experimentsQuery = useQuery<Experiment[]>({
    queryKey: ['admin', 'experiments', status],
    queryFn: async () => {
      const params = status ? `?status=${encodeURIComponent(status)}` : ''
      const res = await apiFetch(`/admin/experiments${params}`)
      if (!res.ok) throw new Error('获取实验列表失败')
      return res.json() as Promise<Experiment[]>
    },
  })

  const createExperimentMutation = useMutation<Experiment, Error, ExperimentCreatePayload>({
    mutationFn: async (payload) => {
      const res = await apiFetch('/admin/experiments', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '创建实验失败')
      }
      return res.json() as Promise<Experiment>
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'experiments'] })
    },
  })

  const startExperimentMutation = useMutation<Experiment, Error, number>({
    mutationFn: async (experimentId) => {
      const res = await apiFetch(`/admin/experiments/${experimentId}/start`, {
        method: 'POST',
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '启动实验失败')
      }
      return res.json() as Promise<Experiment>
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'experiments'] })
    },
  })

  const pauseExperimentMutation = useMutation<Experiment, Error, number>({
    mutationFn: async (experimentId) => {
      const res = await apiFetch(`/admin/experiments/${experimentId}/pause`, {
        method: 'POST',
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '暂停实验失败')
      }
      return res.json() as Promise<Experiment>
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'experiments'] })
    },
  })

  const archiveExperimentMutation = useMutation<Experiment, Error, number>({
    mutationFn: async (experimentId) => {
      const res = await apiFetch(`/admin/experiments/${experimentId}/archive`, {
        method: 'POST',
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '归档实验失败')
      }
      return res.json() as Promise<Experiment>
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'experiments'] })
    },
  })

  return {
    experiments: experimentsQuery.data ?? [],
    isLoading: experimentsQuery.isLoading,
    error: experimentsQuery.error,
    createExperiment: createExperimentMutation.mutateAsync,
    isCreating: createExperimentMutation.isPending,
    startExperiment: startExperimentMutation.mutateAsync,
    isStarting: startExperimentMutation.isPending,
    pauseExperiment: pauseExperimentMutation.mutateAsync,
    isPausing: pauseExperimentMutation.isPending,
    archiveExperiment: archiveExperimentMutation.mutateAsync,
    isArchiving: archiveExperimentMutation.isPending,
  }
}

export function useExperimentResults(experimentId: number | undefined) {
  return useQuery<ExperimentResult[]>({
    queryKey: ['admin', 'experiments', experimentId, 'results'],
    queryFn: async () => {
      const res = await apiFetch(`/admin/experiments/${experimentId}/results`)
      if (!res.ok) throw new Error('获取实验结果失败')
      return res.json() as Promise<ExperimentResult[]>
    },
    enabled: !!experimentId,
  })
}
