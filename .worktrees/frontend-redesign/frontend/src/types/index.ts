// ==================== API 类型 ====================

export interface User {
  user_id: string;
  username: string;
  role: 'CUSTOMER' | 'ADMIN';
  token: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  user_id: string;
  username: string;
  role: string;
  token: string;
}

// ==================== 聊天类型 ====================

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  metadata?: {
    order_data?: OrderData;
    action_result?: ActionResult;
    error?: string;
  };
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  user_id: string;
}

export interface ChatStreamEvent {
  type: 'delta' | 'complete' | 'error';
  content?: string;
  full_response?: string;
  error?: string;
}

export interface OrderData {
  order_sn: string;
  total_amount: number;
  status: string;
  items: Array<{
    name: string;
    qty: number;
    price: number;
  }>;
}

export interface ActionResult {
  action: string;
  success: boolean;
  message: string;
}

// ==================== 审核任务类型 ====================

export type TaskStatus = 'PENDING' | 'APPROVED' | 'REJECTED';
export type RiskLevel = 'HIGH' | 'MEDIUM' | 'LOW';

export interface Task {
  audit_log_id: number;
  user_id: string;
  session_id: string;
  action_type: string;
  trigger_reason: string;
  risk_level: RiskLevel;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
  admin_id?: string;
  admin_comment?: string;
  context_snapshot?: {
    question: string;
    order_data?: OrderData;
    action_result?: ActionResult;
  };
}

export interface TaskFilters {
  status?: TaskStatus | 'ALL';
  riskLevel?: RiskLevel | 'ALL';
}

export interface DecisionRequest {
  audit_log_id: number;
  action: 'APPROVE' | 'REJECT';
  admin_id: string;
  comment: string;
}

// ==================== WebSocket 类型 ====================

export interface WebSocketMessage {
  type: 'notification' | 'task_update' | 'ping' | 'pong';
  payload?: Task | Notification;
  timestamp: string;
}

export interface Notification {
  id: string;
  type: 'info' | 'warning' | 'success' | 'error';
  title: string;
  message: string;
  task_id?: number;
  timestamp: Date;
  read: boolean;
}

// ==================== 组件 Props 类型 ====================

export interface BaseProps {
  className?: string;
  children?: React.ReactNode;
}
