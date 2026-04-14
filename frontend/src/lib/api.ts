import { useAuthStore } from '@/stores/auth'

export const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export interface ApiFetchOptions extends RequestInit {
  skipAuth?: boolean
  skip401Redirect?: boolean
}

export function getApiHeaders(contentType = true): Record<string, string> {
  const token = useAuthStore.getState().token
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token || ''}`,
  }
  if (contentType) {
    headers['Content-Type'] = 'application/json'
  }
  return headers
}

export async function apiFetch(input: string, init?: ApiFetchOptions): Promise<Response> {
  const url = input.startsWith('http') ? input : `${API_BASE}${input}`
  const isFormData = init?.body instanceof FormData
  const headers: Record<string, string> = {
    ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
    ...(init?.skipAuth ? {} : { Authorization: `Bearer ${useAuthStore.getState().token || ''}` }),
    ...((init?.headers as Record<string, string> | undefined) || {}),
  }
  const res = await fetch(url, { ...init, headers })
  if (res.status === 401 && !init?.skip401Redirect) {
    useAuthStore.getState().logout()
    window.location.href = '/'
    throw new Error('登录已过期，请重新登录')
  }
  return res
}
