import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import type { KnowledgeDocument, KnowledgeUploadResult, SyncStatus } from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export function useKnowledgeBase() {
  const queryClient = useQueryClient()

  const { data: documents, isLoading } = useQuery<KnowledgeDocument[]>({
    queryKey: ['admin', 'knowledge'],
    queryFn: async () => {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/knowledge`, {
        headers: { Authorization: `Bearer ${token || ''}` },
      })
      if (!res.ok) throw new Error('获取知识库列表失败')
      return res.json() as Promise<KnowledgeDocument[]>
    },
  })

  const uploadMutation = useMutation<KnowledgeUploadResult, Error, File>({
    mutationFn: async (file) => {
      const token = useAuthStore.getState().token
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch(`${API_BASE}/admin/knowledge`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token || ''}` },
        body: formData,
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '上传失败')
      }
      return res.json() as Promise<KnowledgeUploadResult>
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'knowledge'] })
    },
  })

  const deleteMutation = useMutation<void, Error, number>({
    mutationFn: async (docId) => {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/knowledge/${docId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token || ''}` },
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '删除失败')
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'knowledge'] })
    },
  })

  const syncMutation = useMutation<KnowledgeUploadResult, Error, number>({
    mutationFn: async (docId) => {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/knowledge/${docId}/sync`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token || ''}` },
      })
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(err.detail || '同步失败')
      }
      return res.json() as Promise<KnowledgeUploadResult>
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'knowledge'] })
    },
  })

  return {
    documents: documents ?? [],
    isLoading,
    uploadDocument: uploadMutation.mutateAsync,
    isUploading: uploadMutation.isPending,
    deleteDocument: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,
    syncDocument: syncMutation.mutateAsync,
    isSyncing: syncMutation.isPending,
  }
}

export function useSyncStatus(taskId: string | null) {
  return useQuery<SyncStatus>({
    queryKey: ['admin', 'knowledge', 'sync', taskId],
    queryFn: async () => {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/admin/knowledge/sync/${taskId}`, {
        headers: { Authorization: `Bearer ${token || ''}` },
      })
      if (!res.ok) throw new Error('获取同步状态失败')
      return res.json() as Promise<SyncStatus>
    },
    enabled: !!taskId,
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 2000
      if (data.status === 'PENDING' || data.status === 'STARTED') return 2000
      return false
    },
  })
}
