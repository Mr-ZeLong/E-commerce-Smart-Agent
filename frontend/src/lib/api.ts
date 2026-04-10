import { useAuthStore } from '@/stores/auth'

export const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export function getApiHeaders(): Record<string, string> {
  const token = useAuthStore.getState().token
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token || ''}`,
  }
}
