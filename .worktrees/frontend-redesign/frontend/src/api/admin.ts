import { apiClient } from './client';
import type { Task, TaskFilters, DecisionRequest } from '@/types';

export const adminApi = {
  // Get pending tasks with filters
  getTasks: async (filters: TaskFilters = {}): Promise<Task[]> => {
    const params = new URLSearchParams();
    if (filters.status && filters.status !== 'ALL') {
      params.append('status', filters.status);
    }
    if (filters.riskLevel && filters.riskLevel !== 'ALL') {
      params.append('risk_level', filters.riskLevel);
    }

    const response = await apiClient.get<Task[]>(
      `/admin/tasks?${params.toString()}`
    );
    return response.data;
  },

  // Get task details
  getTask: async (auditLogId: number): Promise<Task> => {
    const response = await apiClient.get<Task>(`/admin/tasks/${auditLogId}`);
    return response.data;
  },

  // Submit decision
  submitDecision: async (data: DecisionRequest): Promise<void> => {
    await apiClient.post('/admin/decision', data);
  },

  // Get task statistics
  getStats: async (): Promise<{
    pending: number;
    approved: number;
    rejected: number;
    high_risk: number;
  }> => {
    const response = await apiClient.get('/admin/stats');
    return response.data;
  },
};
