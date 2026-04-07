import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '@/api/admin';
import type { TaskFilters } from '@/types';

export function useTasks(filters: TaskFilters = {}) {
  const queryClient = useQueryClient();

  const tasksQuery = useQuery({
    queryKey: ['tasks', filters],
    queryFn: () => adminApi.getTasks(filters),
  });

  const decisionMutation = useMutation({
    mutationFn: adminApi.submitDecision,
    onSuccess: () => {
      // Invalidate and refetch tasks after decision
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['taskStats'] });
    },
  });

  return {
    tasks: tasksQuery.data || [],
    isLoading: tasksQuery.isLoading,
    isError: tasksQuery.isError,
    error: tasksQuery.error,
    refetch: tasksQuery.refetch,
    submitDecision: decisionMutation.mutateAsync,
    isSubmitting: decisionMutation.isPending,
  };
}

export function useTaskStats() {
  return useQuery({
    queryKey: ['taskStats'],
    queryFn: adminApi.getStats,
  });
}
