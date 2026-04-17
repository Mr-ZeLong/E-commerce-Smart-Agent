import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api'

export interface DashboardSummary {
  total_sessions_24h: number
  total_sessions_7d: number
  avg_confidence_24h: number | null
  transfer_rate_24h: number
  avg_latency_ms_24h: number | null
  containment_rate_24h: number
  token_efficiency_24h: number | null
}

export interface IntentAccuracyTrendItem {
  hour: string
  intent_category: string
  total: number
  correct: number
  accuracy: number
}

export interface TransferReasonItem {
  reason: string
  count: number
  percentage: number
}

export interface TokenUsageItem {
  date: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
}

export interface LatencyTrendItem {
  hour: string
  avg_latency_ms: number
  p95_latency_ms: number
  p99_latency_ms: number
}

export interface AlertItem {
  metric: string
  severity: string
  message: string
  value: number
  threshold: number
}

export function useDashboardSummary(hours = 24) {
  return useQuery<DashboardSummary>({
    queryKey: ['admin', 'metrics', 'summary', hours],
    queryFn: async () => {
      const res = await apiFetch(`/admin/metrics/dashboard/summary?hours=${hours}`)
      if (!res.ok) {
        throw new Error('获取监控摘要失败')
      }
      return res.json() as Promise<DashboardSummary>
    },
    refetchInterval: 30000,
  })
}

export function useIntentAccuracyTrend(hours = 24) {
  return useQuery<IntentAccuracyTrendItem[]>({
    queryKey: ['admin', 'metrics', 'intent-accuracy', hours],
    queryFn: async () => {
      const res = await apiFetch(`/admin/metrics/dashboard/intent-accuracy?hours=${hours}`)
      if (!res.ok) {
        throw new Error('获取意图准确率趋势失败')
      }
      return res.json() as Promise<IntentAccuracyTrendItem[]>
    },
  })
}

export function useTransferReasons(days = 7) {
  return useQuery<TransferReasonItem[]>({
    queryKey: ['admin', 'metrics', 'transfer-reasons', days],
    queryFn: async () => {
      const res = await apiFetch(`/admin/metrics/dashboard/transfer-reasons?days=${days}`)
      if (!res.ok) {
        throw new Error('获取转接原因失败')
      }
      return res.json() as Promise<TransferReasonItem[]>
    },
  })
}

export function useTokenUsage(days = 7) {
  return useQuery<TokenUsageItem[]>({
    queryKey: ['admin', 'metrics', 'token-usage', days],
    queryFn: async () => {
      const res = await apiFetch(`/admin/metrics/dashboard/token-usage?days=${days}`)
      if (!res.ok) {
        throw new Error('获取Token使用量失败')
      }
      return res.json() as Promise<TokenUsageItem[]>
    },
  })
}

export function useLatencyTrend(hours = 24) {
  return useQuery<LatencyTrendItem[]>({
    queryKey: ['admin', 'metrics', 'latency-trend', hours],
    queryFn: async () => {
      const res = await apiFetch(`/admin/metrics/dashboard/latency-trend?hours=${hours}`)
      if (!res.ok) {
        throw new Error('获取延迟趋势失败')
      }
      return res.json() as Promise<LatencyTrendItem[]>
    },
  })
}

export interface RAGPrecisionItem {
  date: string
  avg_score: number
  count: number
}

export interface HallucinationRateItem {
  date: string
  hallucination_rate: number
  sampled_count: number
}

export function useRAGPrecision(days = 7) {
  return useQuery<RAGPrecisionItem[]>({
    queryKey: ['admin', 'metrics', 'rag-precision', days],
    queryFn: async () => {
      const res = await apiFetch(`/admin/metrics/dashboard/rag-precision?days=${days}`)
      if (!res.ok) {
        throw new Error('获取RAG精度失败')
      }
      return res.json() as Promise<RAGPrecisionItem[]>
    },
  })
}

export function useHallucinationRate(days = 7) {
  return useQuery<HallucinationRateItem[]>({
    queryKey: ['admin', 'metrics', 'hallucination-rate', days],
    queryFn: async () => {
      const res = await apiFetch(`/admin/metrics/dashboard/hallucination-rate?days=${days}`)
      if (!res.ok) {
        throw new Error('获取幻觉率失败')
      }
      return res.json() as Promise<HallucinationRateItem[]>
    },
  })
}

export function useDashboardAlerts(hours = 24) {
  return useQuery<AlertItem[]>({
    queryKey: ['admin', 'metrics', 'alerts', hours],
    queryFn: async () => {
      const res = await apiFetch(`/admin/metrics/dashboard/alerts?hours=${hours}`)
      if (!res.ok) {
        throw new Error('获取告警信息失败')
      }
      return res.json() as Promise<AlertItem[]>
    },
    refetchInterval: 60000,
  })
}
