import { useQuery } from '@tanstack/react-query'
import type { CSATTrend, ComplaintRootCause, AgentComparison, TraceListResponse } from '@/types'
import { apiFetch } from '@/lib/api'


export function useCSATTrend(days = 30) {
  return useQuery<CSATTrend[]>({
    queryKey: ['admin', 'analytics', 'csat', days],
    queryFn: async () => {
      const res = await apiFetch(`/admin/analytics/csat?days=${days}`)
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
      const res = await apiFetch('/admin/analytics/complaint-root-causes')
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
      const res = await apiFetch(`/admin/analytics/agent-comparison?days=${days}`)
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
      const res = await apiFetch(`/admin/analytics/traces?days=${days}&offset=${offset}&limit=${limit}`)
      if (!res.ok) {
        throw new Error('获取追踪数据失败')
      }
      return res.json() as Promise<TraceListResponse>
    },
  })
}
