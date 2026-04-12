export interface User {
  user_id: number | string
  username: string
  email?: string
  full_name?: string
  role: 'ADMIN' | 'USER'
  is_admin?: boolean
}

export interface Task {
  audit_log_id: number
  thread_id: string
  user_id: number
  refund_application_id?: number
  order_id?: number
  trigger_reason: string
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW'
  context_snapshot: {
    question?: string
    order_data?: {
      order_sn: string
      total_amount: number
      status: string
      items: { name: string; qty: number }[]
    }
  } | null
  created_at: string
}

export interface TaskFilters {
  riskLevel: 'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'
}

export interface Notification {
  id: string
  title: string
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
  read: boolean
  created_at?: string
}

export interface LoginCredentials {
  username: string
  password: string
}

export interface TaskStats {
  pending: number
  high_risk: number
}

export interface SessionMetrics {
  '24h': number
  '7d': number
  '30d': number
}

export interface TransferMetric {
  final_agent: string
  total: number
  transfers: number
  transfer_rate: number
}

export interface ConfidenceMetric {
  final_agent: string
  avg_confidence: number | null
}

export interface LatencyMetric {
  node_name: string
  p99_latency_ms: number | null
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  isStreaming?: boolean
}

export interface ConversationThread {
  thread_id: string
  user_id: number | null
  message_count: number
  last_updated: string
  intent_category?: string | null
}

export interface ConversationMessage {
  id: number
  thread_id: string
  sender_type: string
  sender_id: number | null
  content: Record<string, unknown>
  message_type: string
  created_at: string
  meta_data?: Record<string, unknown> | null
}

export interface ConversationList {
  threads: ConversationThread[]
  total: number
  offset: number
  limit: number
}

export interface GoldenRecord {
  query: string
  expected_intent: string
  expected_slots: Record<string, string>
  expected_answer_fragment: string
  expected_audit_level?: string
}

export interface EvaluationDatasetResponse {
  total: number
  limit: number
  offset: number
  records: GoldenRecord[]
}

export interface EvaluationResults {
  intent_accuracy: number
  slot_recall: number
  rag_precision: number
  answer_correctness: number
  total_records: number
}

export interface KnowledgeDocument {
  id: number
  filename: string
  content_type: string
  doc_size_bytes: number | null
  sync_status: string
  sync_message: string | null
  last_synced_at: string | null
  created_at: string
  updated_at: string
}

export interface KnowledgeUploadResult {
  id: number
  filename: string
  sync_status: string
  task_id: string | null
}

export interface SyncStatus {
  task_id: string
  status: string
  result: Record<string, unknown> | null
}
