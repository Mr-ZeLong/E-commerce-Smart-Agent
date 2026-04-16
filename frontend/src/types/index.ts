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
  feedbackSentiment?: 'up' | 'down' | null
  messageIndex?: number
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

export interface AgentConfig {
  agent_name: string
  system_prompt: string
  previous_system_prompt: string | null
  confidence_threshold: number
  max_retries: number
  enabled: boolean
  updated_at: string
}

export interface AgentConfigPayload {
  system_prompt?: string
  confidence_threshold?: number
  max_retries?: number
  enabled?: boolean
}

export interface RoutingRule {
  id: number
  intent_category: string
  target_agent: string
  priority: number
  condition_json: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface AgentConfigAuditLog {
  id: number
  agent_name: string
  changed_by: number
  field_name: string
  old_value: string | null
  new_value: string | null
  created_at: string
}

export interface AgentsConfigResponse {
  configs: AgentConfig[]
  routing_rules: RoutingRule[]
}

export interface ComplaintTicket {
  id: number
  user_id: number
  thread_id: string
  category: string
  urgency: 'low' | 'medium' | 'high'
  status: 'open' | 'in_progress' | 'resolved' | 'closed'
  assigned_to: number | null
  created_at: string
  updated_at: string
  order_sn: string | null
  description: string
  expected_resolution: string | null
}

export interface ComplaintFilters {
  status?: 'open' | 'in_progress' | 'resolved' | 'closed'
  urgency?: 'low' | 'medium' | 'high'
  assigned_to?: number
  offset?: number
  limit?: number
}

export interface ComplaintListResponse {
  tickets: ComplaintTicket[]
  total: number
  offset: number
  limit: number
}

// Analytics V2 Types
export interface CSATTrend {
  date: string
  avg_score: number
  count: number
}

export interface ComplaintRootCause {
  category: string
  count: number
}

export interface AgentComparison {
  final_agent: string
  total_sessions: number
  avg_confidence: number | null
  transfer_rate: number | null
  avg_latency_ms: number | null
  complaint_count: number | null
}

export interface Trace {
  id: string
  thread_id: string
  user_id: number | null
  intent_category: string | null
  final_agent: string | null
  confidence_score: number | null
  needs_human_transfer: boolean | null
  langsmith_run_url: string | null
  created_at: string
  total_latency_ms: number | null
}

export interface TraceListResponse {
  traces: Trace[]
  total: number
  limit: number
  offset: number
}

export interface FeedbackItem {
  id: number
  user_id: number
  thread_id: string
  message_index: number
  score: number
  comment: string | null
  created_at: string
}

export interface FeedbackFilters {
  sentiment?: string
  date_from?: string
  date_to?: string
  offset?: number
  limit?: number
}

export interface FeedbackListResponse {
  items: FeedbackItem[]
  total: number
  offset: number
  limit: number
}

// Experiment types
export interface Experiment {
  id: number
  name: string
  description: string | null
  status: 'draft' | 'running' | 'paused' | 'completed'
  created_at: string
  updated_at: string
}

export interface ExperimentVariant {
  name: string
  weight: number
  system_prompt?: string | null
  llm_model?: string | null
  retriever_top_k?: number | null
  reranker_enabled?: boolean | null
  extra_config?: Record<string, unknown> | null
}

export interface ExperimentCreatePayload {
  name: string
  description?: string | null
  variants: ExperimentVariant[]
}

export interface ExperimentResult {
  variant_id: number
  variant_name: string
  weight: number
  assignments: number
}

// WebSocket types
export interface WSMessage {
  type: string
  data?: Record<string, unknown>
  [key: string]: unknown
}

export interface WSNotification extends WSMessage {
  type: 'notification'
  title: string
  message: string
  severity: 'success' | 'error' | 'warning' | 'info'
  timestamp?: string
}
