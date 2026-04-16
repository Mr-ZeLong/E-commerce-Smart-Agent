import { useMutation, useQuery } from '@tanstack/react-query'
import type { FeedbackListResponse, FeedbackFilters, CSATTrend } from '@/types'
import { apiFetch } from '@/lib/api'

export function useFeedbackList(filters: FeedbackFilters = {}) {
  return useQuery<FeedbackListResponse>({
    queryKey: ['admin', 'feedback', filters],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filters.sentiment) params.append('sentiment', filters.sentiment)
      if (filters.date_from) params.append('date_from', filters.date_from)
      if (filters.date_to) params.append('date_to', filters.date_to)
      if (filters.offset !== undefined) params.append('offset', String(filters.offset))
      if (filters.limit !== undefined) params.append('limit', String(filters.limit))

      const queryString = params.toString()
      const res = await apiFetch(`/admin/feedback${queryString ? `?${queryString}` : ''}`)
      if (!res.ok) {
        throw new Error('获取反馈列表失败')
      }
      return res.json() as Promise<FeedbackListResponse>
    },
  })
}

export function useExportFeedback() {
  return useMutation<{ content: string; filename: string }, Error, FeedbackFilters | undefined>({
    mutationFn: async (filters = {}) => {
      const params = new URLSearchParams()
      if (filters.sentiment) params.append('sentiment', filters.sentiment)
      if (filters.date_from) params.append('date_from', filters.date_from)
      if (filters.date_to) params.append('date_to', filters.date_to)

      const queryString = params.toString()
      const res = await apiFetch(`/admin/feedback/export${queryString ? `?${queryString}` : ''}`)
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '导出失败')
      }
      return res.json() as Promise<{ content: string; filename: string }>
    },
  })
}

export function useCSATTrend(days = 30) {
  return useQuery<{ days: number; trend: CSATTrend[] }>({
    queryKey: ['admin', 'feedback', 'csat', days],
    queryFn: async () => {
      const res = await apiFetch(`/admin/feedback/csat?days=${days}`)
      if (!res.ok) {
        throw new Error('获取CSAT趋势失败')
      }
      return res.json() as Promise<{ days: number; trend: CSATTrend[] }>
    },
  })
}

export function useRunQualityScore() {
  return useMutation<{ success: boolean; scored_count: number }, Error, { sample_size: number }>({
    mutationFn: async ({ sample_size }) => {
      const res = await apiFetch('/admin/feedback/quality-score/run', {
        method: 'POST',
        body: JSON.stringify({ sample_size }),
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '运行质量评分失败')
      }
      return res.json() as Promise<{ success: boolean; scored_count: number }>
    },
  })
}
