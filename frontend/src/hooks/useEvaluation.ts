import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { EvaluationResults, EvaluationDatasetResponse } from '@/types'
import { apiFetch } from '@/lib/api'


export function useEvaluationDataset(limit = 20, offset = 0) {
  return useQuery<EvaluationDatasetResponse>({
    queryKey: ['admin', 'evaluation', 'dataset', limit, offset],
    queryFn: async () => {
      const res = await apiFetch(`/admin/evaluation/dataset?limit=${limit}&offset=${offset}`)
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
      const res = await apiFetch('/admin/evaluation/run', {
        method: 'POST',
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
