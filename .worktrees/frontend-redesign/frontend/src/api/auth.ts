import { apiClient } from './client';
import type { LoginRequest, LoginResponse } from '@/types';

export const authApi = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>('/auth/login', data);
    return response.data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout');
  },

  getCurrentUser: async (): Promise<LoginResponse> => {
    const response = await apiClient.get<LoginResponse>('/auth/me');
    return response.data;
  },
};
