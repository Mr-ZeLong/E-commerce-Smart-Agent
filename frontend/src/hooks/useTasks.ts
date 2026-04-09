import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/stores/auth';
import type { Task, TaskFilters, TaskStats } from '@/types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

interface SubmitDecisionPayload {
  audit_log_id: number;
  action: 'APPROVE' | 'REJECT';
  comment: string;
  admin_id?: string | number;
}

interface TaskStatsResponse {
  risk_tasks: number;
  confidence_tasks: number;
  manual_tasks: number;
  total: number;
}

export function useTasks(filters: TaskFilters) {
  const queryClient = useQueryClient();

  const { data: tasks, isLoading } = useQuery<Task[]>({
    queryKey: ['admin', 'tasks', filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.riskLevel && filters.riskLevel !== 'ALL') {
        params.append('risk_level', filters.riskLevel);
      }
      const token = useAuthStore.getState().token;
      const res = await fetch(`${API_BASE}/admin/tasks?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token || ''}`,
        },
      });
      if (!res.ok) {
        throw new Error('获取任务列表失败');
      }
      return res.json();
    },
  });

  const { mutateAsync: submitDecision, isPending: isSubmitting } = useMutation({
    mutationFn: async (payload: SubmitDecisionPayload) => {
      const token = useAuthStore.getState().token;
      const res = await fetch(`${API_BASE}/admin/resume/${payload.audit_log_id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token || ''}`,
        },
        body: JSON.stringify({
          action: payload.action,
          admin_comment: payload.comment,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || '提交决策失败');
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'tasks'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'taskStats'] });
    },
  });

  return {
    tasks: tasks ?? [],
    isLoading,
    submitDecision,
    isSubmitting,
  };
}

export function useTaskStats() {
  return useQuery<TaskStats>({
    queryKey: ['admin', 'taskStats'],
    queryFn: async () => {
      const token = useAuthStore.getState().token;
      const res = await fetch(`${API_BASE}/admin/tasks-all`, {
        headers: {
          Authorization: `Bearer ${token || ''}`,
        },
      });
      if (!res.ok) {
        throw new Error('获取统计失败');
      }
      const data: TaskStatsResponse = await res.json();
      return {
        pending: data.total,
        high_risk: data.risk_tasks,
      };
    },
  });
}
