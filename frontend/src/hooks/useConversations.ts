import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import type { ConversationList, ConversationMessage } from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export interface ConversationFilters {
  user_id?: string
  intent_category?: string
  start_date?: string
  end_date?: string
}

export function useConversations(filters: ConversationFilters, offset = 0, limit = 20) {
  const { data, isLoading } = useQuery<ConversationList>({
    queryKey: ['admin', 'conversations', filters, offset, limit],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.append('offset', String(offset))
      params.append('limit', String(limit))
      if (filters.user_id) {
        params.append('user_id', filters.user_id)
      }
      if (filters.intent_category) {
        params.append('intent_category', filters.intent_category)
      }
      if (filters.start_date) {
        params.append('start_date', filters.start_date)
      }
      if (filters.end_date) {
        params.append('end_date', filters.end_date)
      }
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/conversations?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token || ''}`,
        },
      })
      if (!res.ok) {
        throw new Error('获取会话列表失败')
      }
      return res.json() as Promise<ConversationList>
    },
  })

  return {
    conversations: data?.threads ?? [],
    total: data?.total ?? 0,
    isLoading,
  }
}

export function useConversationMessages(threadId: string | null) {
  const { data: messages, isLoading } = useQuery<ConversationMessage[]>({
    queryKey: ['admin', 'conversation', threadId],
    enabled: !!threadId,
    queryFn: async () => {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/conversations/${threadId}`, {
        headers: {
          Authorization: `Bearer ${token || ''}`,
        },
      })
      if (!res.ok) {
        throw new Error('获取会话消息失败')
      }
      return res.json() as Promise<ConversationMessage[]>
    },
  })

  return {
    messages: messages ?? [],
    isLoading,
  }
}
