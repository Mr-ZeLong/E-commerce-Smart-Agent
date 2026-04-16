import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { AgentConfig, AgentsConfigResponse, AgentConfigPayload, AgentConfigAuditLog, AgentConfigVersion, AgentConfigVersionMetrics, PromptEffectReport, RoutingRule } from '@/types'
import { apiFetch } from '@/lib/api'

export function useAgentAuditLog(agentName: string | undefined) {
  return useQuery<AgentConfigAuditLog[]>({
    queryKey: ['admin', 'agents', 'config', agentName, 'audit-log'],
    queryFn: async () => {
      const res = await apiFetch(`/admin/agents/config/${agentName}/audit-log`)
      if (!res.ok) throw new Error('获取审计日志失败')
      return res.json() as Promise<AgentConfigAuditLog[]>
    },
    enabled: !!agentName,
  })
}

export function useAgentVersions(agentName: string | undefined) {
  return useQuery<AgentConfigVersion[]>({
    queryKey: ['admin', 'agents', 'config', agentName, 'versions'],
    queryFn: async () => {
      const res = await apiFetch(`/admin/agents/config/${agentName}/versions`)
      if (!res.ok) throw new Error('获取版本历史失败')
      return res.json() as Promise<AgentConfigVersion[]>
    },
    enabled: !!agentName,
  })
}

export function useAgentVersionMetrics(agentName: string | undefined, versionId: number | undefined) {
  return useQuery<AgentConfigVersionMetrics>({
    queryKey: ['admin', 'agents', 'config', agentName, 'versions', versionId, 'metrics'],
    queryFn: async () => {
      const res = await apiFetch(`/admin/agents/config/${agentName}/versions/${versionId}/metrics`)
      if (!res.ok) throw new Error('获取版本指标失败')
      return res.json() as Promise<AgentConfigVersionMetrics>
    },
    enabled: !!agentName && !!versionId,
  })
}

export function useAgentReports(agentName: string | undefined) {
  return useQuery<PromptEffectReport[]>({
    queryKey: ['admin', 'agents', 'config', agentName, 'reports'],
    queryFn: async () => {
      const res = await apiFetch(`/admin/agents/config/${agentName}/reports`)
      if (!res.ok) throw new Error('获取月度报告失败')
      return res.json() as Promise<PromptEffectReport[]>
    },
    enabled: !!agentName,
  })
}

export function useAgentConfig() {
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery<AgentsConfigResponse>({
    queryKey: ['admin', 'agents', 'config'],
    queryFn: async () => {
      const res = await apiFetch('/admin/agents/config')
      if (!res.ok) throw new Error('获取 Agent 配置失败')
      return res.json() as Promise<AgentsConfigResponse>
    },
  })

  const updateRoutingRuleMutation = useMutation<
    RoutingRule,
    Error,
    { id?: number; intent_category: string; target_agent: string; priority: number; condition_json?: Record<string, unknown> },
    { previousData: AgentsConfigResponse | undefined }
  >({
    mutationFn: async (payload) => {
      const res = await apiFetch(
        payload.id ? `/admin/agents/routing-rules/${payload.id}` : '/admin/agents/routing-rules',
        {
          method: payload.id ? 'PUT' : 'POST',
          body: JSON.stringify(payload),
        }
      )
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '保存失败')
      }
      return (await res.json()) as RoutingRule
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'agents', 'config'] })
    },
  })

  const deleteRoutingRuleMutation = useMutation<{ success: boolean; message: string }, Error, number>({
    mutationFn: async (id) => {
      const res = await apiFetch(`/admin/agents/routing-rules/${id}`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '删除失败')
      }
      return res.json() as Promise<{ success: boolean; message: string }>
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'agents', 'config'] })
    },
  })

  const updateMutation = useMutation<
    AgentConfig,
    Error,
    { agentName: string; payload: AgentConfigPayload },
    { previousData: AgentsConfigResponse | undefined }
  >({
    mutationFn: async ({ agentName, payload }) => {
      const res = await apiFetch(`/admin/agents/config/${agentName}`, {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '更新失败')
      }
      return res.json() as Promise<AgentConfig>
    },
    onMutate: async ({ agentName, payload }) => {
      await queryClient.cancelQueries({ queryKey: ['admin', 'agents', 'config'] })
      const previousData = queryClient.getQueryData<AgentsConfigResponse>(['admin', 'agents', 'config'])
      queryClient.setQueryData<AgentsConfigResponse>(['admin', 'agents', 'config'], (old) => {
        if (!old) return old
        return {
          ...old,
          configs: old.configs.map((agent) =>
            agent.agent_name === agentName ? { ...agent, ...payload } : agent
          ),
        }
      })
      return { previousData }
    },
    onError: (_err, _variables, context) => {
      if (context?.previousData) {
        queryClient.setQueryData(['admin', 'agents', 'config'], context.previousData)
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'agents', 'config'] })
    },
  })

  const rollbackMutation = useMutation<AgentConfig, Error, string>({
    mutationFn: async (agentName) => {
      const res = await apiFetch(`/admin/agents/config/${agentName}/rollback`, {
        method: 'POST',
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '回滚失败')
      }
      return res.json() as Promise<AgentConfig>
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'agents', 'config'] })
    },
  })

  const rollbackToVersionMutation = useMutation<AgentConfig, Error, { agentName: string; versionId: number }>({
    mutationFn: async ({ agentName, versionId }) => {
      const res = await apiFetch(`/admin/agents/config/${agentName}/versions/${versionId}/rollback`, {
        method: 'POST',
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '回滚失败')
      }
      return res.json() as Promise<AgentConfig>
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'agents', 'config'] })
      void queryClient.invalidateQueries({ queryKey: ['admin', 'agents', 'config', variables.agentName, 'versions'] })
    },
  })

  const generateReportMutation = useMutation<
    { task_id: string; agent_name: string; report_month: string },
    Error,
    { agentName: string; reportMonth: string }
  >({
    mutationFn: async ({ agentName, reportMonth }) => {
      const res = await apiFetch(`/admin/agents/config/${agentName}/reports/generate`, {
        method: 'POST',
        body: JSON.stringify({ report_month: reportMonth }),
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '生成报告失败')
      }
      return res.json() as Promise<{ task_id: string; agent_name: string; report_month: string }>
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'agents', 'config', variables.agentName, 'reports'] })
    },
  })

  return {
    agents: data?.configs ?? [],
    routingRules: data?.routing_rules ?? [],
    isLoading,
    updateAgent: updateMutation.mutateAsync,
    isUpdating: updateMutation.isPending,
    rollbackAgent: rollbackMutation.mutateAsync,
    isRollingBack: rollbackMutation.isPending,
    rollbackToVersion: rollbackToVersionMutation.mutateAsync,
    isRollingBackToVersion: rollbackToVersionMutation.isPending,
    generateReport: generateReportMutation.mutateAsync,
    isGeneratingReport: generateReportMutation.isPending,
    saveRoutingRule: updateRoutingRuleMutation.mutateAsync,
    isSavingRule: updateRoutingRuleMutation.isPending,
    deleteRoutingRule: deleteRoutingRuleMutation.mutateAsync,
    isDeletingRule: deleteRoutingRuleMutation.isPending,
  }
}
