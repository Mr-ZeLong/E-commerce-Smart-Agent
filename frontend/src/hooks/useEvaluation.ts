import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import type { EvaluationResults, EvaluationDatasetResponse } from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export function useEvaluationDataset(limit = 20, offset = 0) {
  return useQuery<EvaluationDatasetResponse>({
    queryKey: ['admin', 'evaluation', 'dataset', limit, offset],
    queryFn: async () => {
      const token = useAuthStore.getState().token
      const res = await fetch(
        `${API_BASE}/admin/evaluation/dataset?limit=${limit}&offset=${offset}`,
        {
          headers: {
            Authorization: `Bearer ${token || ''}`,
          },
        }
      )
      if (!res.ok) {
        throw new Error('获取评测数据集失败')
      }
      return res.json() as Promise<EvaluationDatasetResponse>
    },
  })
}

export function useRunEvaluation() {
  const queryClient = useQueryClient()

  return useMutation<EvaluationResults, Error, void>({
    mutationFn: async () => {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/evaluation/run`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token || ''}`,
        },
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '运行评测失败')
      }
      return res.json() as Promise<EvaluationResults>
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'evaluation'] })
    },
  })
}
