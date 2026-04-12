import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import type { ComplaintTicket, ComplaintFilters, ComplaintListResponse } from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export function useComplaints(filters: ComplaintFilters = {}) {
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery<ComplaintListResponse>({
    queryKey: ['admin', 'complaints', filters],
    queryFn: async () => {
      const token = useAuthStore.getState().token
      const params = new URLSearchParams()
      
      if (filters.status) params.append('status', filters.status)
      if (filters.urgency) params.append('urgency', filters.urgency)
      if (filters.assigned_to !== undefined) params.append('assigned_to', String(filters.assigned_to))
      if (filters.offset !== undefined) params.append('offset', String(filters.offset))
      if (filters.limit !== undefined) params.append('limit', String(filters.limit))
      
      const queryString = params.toString()
      const url = `${API_BASE}/admin/complaints${queryString ? `?${queryString}` : ''}`
      
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token || ''}` },
      })
      
      if (!res.ok) throw new Error('获取投诉列表失败')
      return res.json() as Promise<ComplaintListResponse>
    },
  })

  const assignMutation = useMutation<
    ComplaintTicket,
    Error,
    { id: number; assigned_to: number },
    { previousData: ComplaintListResponse | undefined }
  >({
    mutationFn: async ({ id, assigned_to }) => {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/complaints/${id}/assign`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token || ''}`,
        },
        body: JSON.stringify({ assigned_to }),
      })
      
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '分配失败')
      }
      return res.json() as Promise<ComplaintTicket>
    },
    onMutate: async ({ id, assigned_to }) => {
      await queryClient.cancelQueries({ queryKey: ['admin', 'complaints', filters] })
      const previousData = queryClient.getQueryData<ComplaintListResponse>(['admin', 'complaints', filters])
      
      queryClient.setQueryData<ComplaintListResponse>(['admin', 'complaints', filters], (old) => {
        if (!old) return old
        return {
          ...old,
          tickets: old.tickets.map((ticket) =>
            ticket.id === id ? { ...ticket, assigned_to } : ticket
          ),
        }
      })
      
      return { previousData }
    },
    onError: (_err, _variables, context) => {
      if (context?.previousData) {
        queryClient.setQueryData(['admin', 'complaints', filters], context.previousData)
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'complaints'] })
    },
  })

  const updateStatusMutation = useMutation<
    ComplaintTicket,
    Error,
    { id: number; status: ComplaintTicket['status'] },
    { previousData: ComplaintListResponse | undefined }
  >({
    mutationFn: async ({ id, status }) => {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/complaints/${id}/status`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token || ''}`,
        },
        body: JSON.stringify({ status }),
      })
      
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '状态更新失败')
      }
      return res.json() as Promise<ComplaintTicket>
    },
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: ['admin', 'complaints', filters] })
      const previousData = queryClient.getQueryData<ComplaintListResponse>(['admin', 'complaints', filters])
      
      queryClient.setQueryData<ComplaintListResponse>(['admin', 'complaints', filters], (old) => {
        if (!old) return old
        return {
          ...old,
          tickets: old.tickets.map((ticket) =>
            ticket.id === id ? { ...ticket, status } : ticket
          ),
        }
      })
      
      return { previousData }
    },
    onError: (_err, _variables, context) => {
      if (context?.previousData) {
        queryClient.setQueryData(['admin', 'complaints', filters], context.previousData)
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'complaints'] })
    },
  })

  const resolveMutation = useMutation<
    ComplaintTicket,
    Error,
    { id: number; resolution_notes: string },
    { previousData: ComplaintListResponse | undefined }
  >({
    mutationFn: async ({ id, resolution_notes }) => {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/complaints/${id}/resolve`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token || ''}`,
        },
        body: JSON.stringify({ resolution_notes }),
      })
      
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '解决失败')
      }
      return res.json() as Promise<ComplaintTicket>
    },
    onMutate: async ({ id }) => {
      await queryClient.cancelQueries({ queryKey: ['admin', 'complaints', filters] })
      const previousData = queryClient.getQueryData<ComplaintListResponse>(['admin', 'complaints', filters])
      
      queryClient.setQueryData<ComplaintListResponse>(['admin', 'complaints', filters], (old) => {
        if (!old) return old
        return {
          ...old,
          tickets: old.tickets.map((ticket) =>
            ticket.id === id ? { ...ticket, status: 'resolved' as const } : ticket
          ),
        }
      })
      
      return { previousData }
    },
    onError: (_err, _variables, context) => {
      if (context?.previousData) {
        queryClient.setQueryData(['admin', 'complaints', filters], context.previousData)
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'complaints'] })
    },
  })

  return {
    tickets: data?.tickets ?? [],
    total: data?.total ?? 0,
    offset: data?.offset ?? 0,
    limit: data?.limit ?? 20,
    isLoading,
    error,
    assign: assignMutation.mutateAsync,
    isAssigning: assignMutation.isPending,
    updateStatus: updateStatusMutation.mutateAsync,
    isUpdatingStatus: updateStatusMutation.isPending,
    resolve: resolveMutation.mutateAsync,
    isResolving: resolveMutation.isPending,
  }
}
