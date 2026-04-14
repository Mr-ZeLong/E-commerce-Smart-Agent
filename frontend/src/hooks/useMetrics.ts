import { useQuery } from '@tanstack/react-query'
import type { SessionMetrics, TransferMetric, ConfidenceMetric, LatencyMetric } from '@/types'
import { apiFetch } from '@/lib/api'


export function useSessionMetrics() {
  return useQuery<SessionMetrics>({
    queryKey: ['admin', 'metrics', 'sessions'],
    queryFn: async () => {
      const res = await apiFetch('/admin/metrics/sessions')
      if (!res.ok) {
        throw new Error('获取会话统计失败')
      }
      return res.json() as Promise<SessionMetrics>
    },
  })
}

export function useTransferMetrics() {
  return useQuery<TransferMetric[]>({
    queryKey: ['admin', 'metrics', 'transfers'],
    queryFn: async () => {
      const res = await apiFetch('/admin/metrics/transfers')
      if (!res.ok) {
        throw new Error('获取转接率统计失败')
      }
      return res.json() as Promise<TransferMetric[]>
    },
  })
}

export function useConfidenceMetrics() {
  return useQuery<ConfidenceMetric[]>({
    queryKey: ['admin', 'metrics', 'confidence'],
    queryFn: async () => {
      const res = await apiFetch('/admin/metrics/confidence')
      if (!res.ok) {
        throw new Error('获取置信度统计失败')
      }
      return res.json() as Promise<ConfidenceMetric[]>
    },
  })
}

export function useLatencyMetrics() {
  return useQuery<LatencyMetric[]>({
    queryKey: ['admin', 'metrics', 'latency'],
    queryFn: async () => {
      const res = await apiFetch('/admin/metrics/latency')
      if (!res.ok) {
        throw new Error('获取延迟统计失败')
      }
      return res.json() as Promise<LatencyMetric[]>
    },
  })
}
