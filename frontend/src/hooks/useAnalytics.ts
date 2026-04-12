import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import type { CSATTrend, ComplaintRootCause, AgentComparison, TraceListResponse } from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export function useCSATTrend(days = 30) {
  return useQuery<CSATTrend[]>({
    queryKey: ['admin', 'analytics', 'csat', days],
    queryFn: async () => {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/analytics/csat?days=${days}`, {
        headers: {
          Authorization: `Bearer ${token || ''}`,
        },
      })
      if (!res.ok) {
        throw new Error('获取 CSAT 趋势失败')
      }
      return res.json() as Promise<CSATTrend[]>
    },
  })
}

export function useComplaintRootCauses() {
  return useQuery<ComplaintRootCause[]>({
    queryKey: ['admin', 'analytics', 'complaint-root-causes'],
    queryFn: async () => {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/analytics/complaint-root-causes`, {
        headers: {
          Authorization: `Bearer ${token || ''}`,
        },
      })
      if (!res.ok) {
        throw new Error('获取投诉根因失败')
      }
      return res.json() as Promise<ComplaintRootCause[]>
    },
  })
}

export function useAgentComparison(days = 30) {
  return useQuery<AgentComparison[]>({
    queryKey: ['admin', 'analytics', 'agent-comparison', days],
    queryFn: async () => {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/analytics/agent-comparison?days=${days}`, {
        headers: {
          Authorization: `Bearer ${token || ''}`,
        },
      })
      if (!res.ok) {
        throw new Error('获取 Agent 对比失败')
      }
      return res.json() as Promise<AgentComparison[]>
    },
  })
}

export function useTraces(days = 7, offset = 0, limit = 20) {
  return useQuery<TraceListResponse>({
    queryKey: ['admin', 'analytics', 'traces', days, offset, limit],
    queryFn: async () => {
      const token = useAuthStore.getState().token
      const res = await fetch(
        `${API_BASE}/admin/analytics/traces?days=${days}&offset=${offset}&limit=${limit}`,
        {
          headers: {
            Authorization: `Bearer ${token || ''}`,
          },
        }
      )
      if (!res.ok) {
        throw new Error('获取追踪数据失败')
      }
      return res.json() as Promise<TraceListResponse>
    },
  })
}
