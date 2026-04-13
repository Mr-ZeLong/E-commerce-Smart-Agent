import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import type { Experiment, ExperimentCreatePayload, ExperimentResult } from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export function useExperiments(status?: string) {
  const queryClient = useQueryClient()

  const experimentsQuery = useQuery<Experiment[]>({
    queryKey: ['admin', 'experiments', status],
    queryFn: async () => {
      const token = useAuthStore.getState().token
      const params = status ? `?status=${encodeURIComponent(status)}` : ''
      const url = `${API_BASE}/admin/experiments${params}`
      
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token || ''}` },
      })
      if (!res.ok) throw new Error('获取实验列表失败')
      return res.json() as Promise<Experiment[]>
    },
  })

  const createExperimentMutation = useMutation<Experiment, Error, ExperimentCreatePayload>({
    mutationFn: async (payload) => {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/experiments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token || ''}`,
        },
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
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/experiments/${experimentId}/start`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token || ''}` },
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
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/experiments/${experimentId}/pause`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token || ''}` },
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
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/experiments/${experimentId}/archive`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token || ''}` },
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
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/experiments/${experimentId}/results`, {
        headers: { Authorization: `Bearer ${token || ''}` },
      })
      if (!res.ok) throw new Error('获取实验结果失败')
      return res.json() as Promise<ExperimentResult[]>
    },
    enabled: !!experimentId,
  })
}