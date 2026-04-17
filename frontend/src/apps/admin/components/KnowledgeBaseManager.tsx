import { useRef, useState } from 'react'
import {
  AlertCircle,
  CheckCircle,
  FileText,
  Loader2,
  RefreshCw,
  Trash2,
  Upload,
  Play,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useKnowledgeBase, useSyncStatus } from '@/hooks/useKnowledgeBase'

function formatBytes(bytes: number | null) {
  if (bytes == null) return '-'
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`
}

function SyncBadge({ status }: { status: string }) {
  if (status === 'done') {
    return (
      <span className="inline-flex items-center gap-1 text-sm text-green-600">
        <CheckCircle className="h-4 w-4" />
        已同步
      </span>
    )
  }
  if (status === 'running' || status === 'STARTED' || status === 'PENDING') {
    return (
      <span className="inline-flex items-center gap-1 text-sm text-blue-600">
        <Loader2 className="h-4 w-4 animate-spin" />
        同步中
      </span>
    )
  }
  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1 text-sm text-red-600">
        <AlertCircle className="h-4 w-4" />
        失败
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-sm text-gray-500">
      <RefreshCw className="h-4 w-4" />
      {status}
    </span>
  )
}

export function KnowledgeBaseManager() {
  const {
    documents,
    isLoading,
    uploadDocument,
    isUploading,
    deleteDocument,
    isDeleting,
    syncDocument,
    isSyncing,
  } = useKnowledgeBase()
  const [lastTaskId, setLastTaskId] = useState<string | null>(null)
  const { data: syncStatus } = useSyncStatus(lastTaskId)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const result = await uploadDocument(file)
      if (result.task_id) setLastTaskId(result.task_id)
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div className="h-full overflow-auto p-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>知识库管理</CardTitle>
          <div className="flex items-center gap-2">
            <input
              type="file"
              ref={fileInputRef}
              className="hidden"
              onChange={(e) => void handleUpload(e)}
              accept=".txt,.md,.json,.pdf"
            />
            <Button onClick={() => fileInputRef.current?.click()} disabled={isUploading}>
              <Upload className="mr-1 h-4 w-4" />
              {isUploading ? '上传中...' : '上传文档'}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {syncStatus && (syncStatus.status === 'PENDING' || syncStatus.status === 'STARTED') && (
            <div className="mb-4 text-sm text-blue-600">
              同步任务 {syncStatus.task_id} 进行中...
            </div>
          )}
          {isLoading ? (
            <div className="text-sm text-gray-500">加载中...</div>
          ) : documents.length === 0 ? (
            <div className="text-sm text-gray-500">暂无文档</div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="h-5 w-5 text-gray-400" />
                    <div>
                      <div className="text-sm font-medium">{doc.filename}</div>
                      <div className="text-xs text-gray-500">
                        {formatBytes(doc.doc_size_bytes)} · {doc.content_type}
                      </div>
                      {doc.sync_message && (
                        <div className="text-xs text-gray-400">{doc.sync_message}</div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <SyncBadge status={doc.sync_status} />
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        void syncDocument(doc.id).then((result) => {
                          if (result.task_id) setLastTaskId(result.task_id)
                        })
                      }}
                      disabled={isSyncing}
                      title="同步到 Qdrant"
                    >
                      <Play className="h-4 w-4 text-blue-500" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        void deleteDocument(doc.id)
                      }}
                      disabled={isDeleting}
                    >
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
