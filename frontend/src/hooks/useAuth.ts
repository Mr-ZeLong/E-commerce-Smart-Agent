import { useMutation } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import { apiFetch } from '@/lib/api'
import type { LoginCredentials, User } from '@/types'

interface LoginResponse {
  access_token: string
  token_type: string
  user_id: number
  username: string
  full_name: string
  is_admin: boolean
}

export function useAuth() {
  const { user, isAuthenticated, logout } = useAuthStore()

  const {
    mutateAsync: login,
    isPending: isLoading,
    error: mutationError,
  } = useMutation({
    mutationFn: async (credentials: LoginCredentials) => {
      const res = await apiFetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials),
        skipAuth: true,
        skip401Redirect: true,
      })
      if (res.status === 401) {
        throw new Error('用户名或密码错误')
      }
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '登录失败')
      }
      return res.json() as Promise<LoginResponse>
    },
    onSuccess: (data) => {
      const userObj: User = {
        user_id: data.user_id,
        username: data.username,
        full_name: data.full_name,
        role: data.is_admin ? 'ADMIN' : 'USER',
        is_admin: data.is_admin,
      }
      useAuthStore.getState().setAuth(data.access_token, userObj)
    },
  })

  const error = mutationError ? mutationError.message : undefined

  return {
    user,
    isAuthenticated,
    logout,
    login,
    isLoading,
    error,
  }
}
