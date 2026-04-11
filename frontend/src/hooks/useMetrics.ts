import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import type { SessionMetrics, TransferMetric, ConfidenceMetric, LatencyMetric } from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export function useSessionMetrics() {
  return useQuery<SessionMetrics>({
    queryKey: ['admin', 'metrics', 'sessions'],
    queryFn: async () => {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/metrics/sessions`, {
        headers: {
          Authorization: `Bearer ${token || ''}`,
        },
      })
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
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/metrics/transfers`, {
        headers: {
          Authorization: `Bearer ${token || ''}`,
        },
      })
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
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/metrics/confidence`, {
        headers: {
          Authorization: `Bearer ${token || ''}`,
        },
      })
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
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/metrics/latency`, {
        headers: {
          Authorization: `Bearer ${token || ''}`,
        },
      })
      if (!res.ok) {
        throw new Error('获取延迟统计失败')
      }
      return res.json() as Promise<LatencyMetric[]>
    },
  })
}
