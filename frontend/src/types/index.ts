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

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  isStreaming?: boolean
}
