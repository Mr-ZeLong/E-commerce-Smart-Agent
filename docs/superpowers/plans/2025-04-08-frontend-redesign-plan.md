# E-commerce Smart Agent 前端重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 Gradio 前端重构为 React + TypeScript + Tailwind CSS + shadcn/ui 现代前端，包含 C 端用户聊天界面和 B 端管理后台。

**Architecture:** 采用嵌入式架构，前端位于 `frontend/` 目录，Vite 多页面构建输出 C 端和 B 端两个入口，生产环境由 FastAPI 静态文件托管。

**Tech Stack:** React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui + Zustand + TanStack Query + React Router v6

---

## 文件结构规划

```
frontend/
├── package.json                    # 依赖配置
├── vite.config.ts                  # Vite 多页面配置
├── tsconfig.json                   # TypeScript 配置
├── tailwind.config.ts              # Tailwind 配置
├── components.json                 # shadcn/ui 配置
├── index.html                      # C 端入口 HTML
├── admin.html                      # B 端入口 HTML
├── src/
│   ├── vite-env.d.ts              # Vite 类型声明
│   ├── globals.css                # 全局样式
│   ├── lib/
│   │   ├── utils.ts               # 工具函数 (cn)
│   │   └── query-client.ts        # TanStack Query 配置
│   ├── types/
│   │   └── index.ts               # 全局类型定义
│   ├── api/
│   │   ├── client.ts              # axios 实例
│   │   ├── auth.ts                # 认证 API
│   │   ├── chat.ts                # 聊天 API (含 SSE)
│   │   └── admin.ts               # 管理 API
│   ├── stores/
│   │   ├── auth.ts                # 认证状态
│   │   ├── websocket.ts           # WebSocket 状态
│   │   └── index.ts               # 导出
│   ├── hooks/
│   │   ├── useAuth.ts             # 认证 hook
│   │   ├── useChat.ts             # 聊天 hook
│   │   ├── useTasks.ts            # 任务 hook
│   │   └── useWebSocket.ts        # WebSocket hook
│   ├── components/
│   │   ├── ui/                    # shadcn/ui 组件
│   │   └── common/                # 共享业务组件
│   │       ├── Layout.tsx
│   │       ├── Loading.tsx
│   │       └── ErrorBoundary.tsx
│   ├── apps/
│   │   ├── customer/
│   │   │   ├── main.tsx           # C 端入口
│   │   │   ├── App.tsx
│   │   │   ├── routes.tsx
│   │   │   ├── pages/
│   │   │   │   ├── Login.tsx
│   │   │   │   └── Chat.tsx
│   │   │   └── components/
│   │   │       ├── ChatMessage.tsx
│   │   │       ├── ChatInput.tsx
│   │   │       ├── OrderCard.tsx
│   │   │       ├── AuditStatusCard.tsx
│   │   │       └── QuickActions.tsx
│   │   └── admin/
│   │       ├── main.tsx           # B 端入口
│   │       ├── App.tsx
│   │       ├── routes.tsx
│   │       ├── pages/
│   │       │   ├── Login.tsx
│   │       │   └── Dashboard.tsx
│   │       └── components/
│   │           ├── TaskList.tsx
│   │           ├── TaskDetail.tsx
│   │           ├── DecisionPanel.tsx
│   │           └── RiskBadge.tsx
│   └── styles/
│       └── globals.css
```

---

## Task 1: 初始化 Vite + React + TypeScript 项目

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`

- [ ] **Step 1: 创建 frontend 目录并初始化**

```bash
cd /home/zelon/projects/E-commerce-Smart-Agent
mkdir -p frontend/src
cd frontend

# 创建完整的 package.json
cat > package.json << 'EOF'
{
  "name": "e-commerce-smart-agent-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.55",
    "@types/react-dom": "^18.2.19",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.35",
    "tailwindcss": "^3.4.1",
    "typescript": "^5.2.2",
    "vite": "^5.1.0"
  }
}
EOF
```

- [ ] **Step 2: 安装核心依赖**

```bash
cd /home/zelon/projects/E-commerce-Smart-Agent/frontend
npm install
```

- [ ] **Step 3: 创建 tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@customer/*": ["./src/apps/customer/*"],
      "@admin/*": ["./src/apps/admin/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 4: 创建 tsconfig.node.json**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

---

## Task 2: 配置 Vite 多页面构建

**Files:**
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/admin.html`
- Create: `frontend/src/vite-env.d.ts`

- [ ] **Step 1: 创建 vite.config.ts**

```typescript
import path from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        customer: path.resolve(__dirname, 'index.html'),
        admin: path.resolve(__dirname, 'admin.html'),
      },
      output: {
        entryFileNames: (chunkInfo) => {
          const name = chunkInfo.name;
          if (name === 'customer' || name === 'admin') {
            return `[name]/[name]-[hash].js`;
          }
          return `shared/[name]-[hash].js`;
        },
        chunkFileNames: 'shared/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          const info = assetInfo.name || '';
          if (info.endsWith('.css')) {
            return '[name]-[hash][extname]';
          }
          return 'assets/[name]-[hash][extname]';
        },
      },
    },
    outDir: 'dist',
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@customer': path.resolve(__dirname, './src/apps/customer'),
      '@admin': path.resolve(__dirname, './src/apps/admin'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

- [ ] **Step 2: 创建 C 端入口 index.html**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Smart Agent - 智能客服</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/apps/customer/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: 创建 B 端入口 admin.html**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Admin Dashboard - 管理后台</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/apps/admin/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 4: 创建 vite-env.d.ts**

```typescript
/// <reference types="vite/client" />
```

---

## Task 3: 配置 Tailwind CSS + shadcn/ui

**Files:**
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/components.json`
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/styles/globals.css`

- [ ] **Step 1: 初始化 Tailwind CSS**

```bash
cd /home/zelon/projects/E-commerce-Smart-Agent/frontend
npx tailwindcss init -p
```

- [ ] **Step 2: 配置 tailwind.config.ts**

```typescript
import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['class'],
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd',
          400: '#60a5fa', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8',
          800: '#1e40af', 900: '#1e3a8a',
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
        secondary: { DEFAULT: 'hsl(var(--secondary))', foreground: 'hsl(var(--secondary-foreground))' },
        destructive: { DEFAULT: 'hsl(var(--destructive))', foreground: 'hsl(var(--destructive-foreground))' },
        muted: { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },
        accent: { DEFAULT: 'hsl(var(--accent))', foreground: 'hsl(var(--accent-foreground))' },
        popover: { DEFAULT: 'hsl(var(--popover))', foreground: 'hsl(var(--popover-foreground))' },
        card: { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};

export default config;
```

- [ ] **Step 3: 安装依赖并初始化 shadcn/ui**

```bash
cd /home/zelon/projects/E-commerce-Smart-Agent/frontend
npm install -D tailwindcss-animate
npm install clsx tailwind-merge
npx shadcn-ui@latest init -y
```

- [ ] **Step 4: 安装 shadcn/ui 组件**

```bash
npx shadcn-ui@latest add button input textarea card badge accordion
npx shadcn-ui@latest add scroll-area separator skeleton
npx shadcn-ui@latest add toast tooltip avatar select label
```

- [ ] **Step 5: 创建 lib/utils.ts**

```typescript
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 6: 创建 globals.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 217 91% 60%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84% 60%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 217 91% 60%;
    --radius: 0.5rem;
  }
}

@layer base {
  * { @apply border-border; }
  body { @apply bg-background text-foreground; }
}
```

---

## Task 4: 配置全局类型定义

**Files:**
- Create: `frontend/src/types/index.ts`

```typescript
export interface User {
  id: number;
  username: string;
  full_name: string;
  is_admin: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  username: string;
  full_name: string;
  is_admin: boolean;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface OrderItem {
  name: string;
  qty: number;
}

export interface Order {
  order_sn: string;
  total_amount: number;
  status: string;
  items: OrderItem[];
}

export interface ContextSnapshot {
  question: string;
  order_data?: Order;
}

export interface Task {
  audit_log_id: number;
  thread_id: string;
  user_id: number;
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  trigger_reason: string;
  context_snapshot: ContextSnapshot;
  created_at: string;
}

export interface TaskFilters {
  riskLevel: 'ALL' | 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface DecisionRequest {
  action: 'APPROVE' | 'REJECT';
  admin_comment: string;
}

export interface SessionStatus {
  status: 'PROCESSING' | 'WAITING_ADMIN' | 'APPROVED' | 'REJECTED';
  data?: {
    trigger_reason?: string;
    risk_level?: string;
    admin_comment?: string;
  };
}

export interface WebSocketMessage {
  type: 'status_update' | 'new_task' | 'task_resolved' | 'pong';
  payload: {
    thread_id?: string;
    status?: string;
    task?: Task;
    message?: string;
  };
}
```

---

## Task 5: 创建 API 客户端

**Files:**
- Create: `frontend/src/lib/query-client.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/api/chat.ts`
- Create: `frontend/src/api/admin.ts`

- [ ] **Step 1: 安装依赖**

```bash
cd /home/zelon/projects/E-commerce-Smart-Agent/frontend
npm install axios @tanstack/react-query lucide-react
```

- [ ] **Step 2: 创建 QueryClient 配置**

```typescript
// src/lib/query-client.ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: 3,
      refetchOnWindowFocus: false,
    },
  },
});
```

- [ ] **Step 3: 创建 API 客户端**

```typescript
// src/api/client.ts
import axios, { AxiosError } from 'axios';
import { useAuthStore } from '@/stores/auth';
import { toast } from '@/components/ui/use-toast';

export const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (!error.response) {
      toast({ title: '网络错误', description: '请检查网络连接', variant: 'destructive' });
      return Promise.reject(error);
    }
    const { status, data } = error.response;
    const message = (data as { detail?: string })?.detail || '未知错误';
    switch (status) {
      case 401:
        useAuthStore.getState().logout();
        window.location.href = '/login';
        toast({ title: '登录已过期', description: '请重新登录', variant: 'destructive' });
        break;
      case 403:
        toast({ title: '权限不足', description: '您没有权限执行此操作', variant: 'destructive' });
        break;
      case 500:
        toast({ title: '服务器错误', description: '请稍后重试', variant: 'destructive' });
        break;
      default:
        toast({ title: '请求失败', description: message, variant: 'destructive' });
    }
    return Promise.reject(error);
  }
);
```

- [ ] **Step 4: 创建 API 模块**

```typescript
// src/api/auth.ts
import { apiClient } from './client';
import type { LoginCredentials, AuthResponse } from '@/types';

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/login', credentials);
    return response.data;
  },
};
```

```typescript
// src/api/chat.ts
import type { SessionStatus } from '@/types';

export interface ChatRequest {
  question: string;
  thread_id: string;
}

export const chatApi = {
  streamChat: async function* (
    request: ChatRequest,
    token: string
  ): AsyncGenerator<string, void, unknown> {
    const response = await fetch('/api/v1/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const reader = response.body?.getReader();
    if (!reader) throw new Error('No response body');
    const decoder = new TextDecoder();
    let buffer = '';
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') return;
            try {
              const parsed = JSON.parse(data);
              if (parsed.token) yield parsed.token;
              if (parsed.error) throw new Error(parsed.error);
            } catch {}
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },
  getStatus: async (threadId: string): Promise<SessionStatus> => {
    const response = await apiClient.get<SessionStatus>(`/status/${threadId}`);
    return response.data;
  },
};
```

```typescript
// src/api/admin.ts
import { apiClient } from './client';
import type { Task, DecisionRequest } from '@/types';

export const adminApi = {
  getTasks: async (riskLevel?: string): Promise<Task[]> => {
    const params = riskLevel && riskLevel !== 'ALL' ? { risk_level: riskLevel } : {};
    const response = await apiClient.get<Task[]>('/admin/tasks', { params });
    return response.data;
  },
  makeDecision: async (
    auditLogId: number,
    decision: DecisionRequest
  ): Promise<{ success: boolean; message: string }> => {
    const response = await apiClient.post<{ success: boolean; message: string }>(
      `/admin/resume/${auditLogId}`,
      decision
    );
    return response.data;
  },
};
```

---

## Task 6: 创建状态管理

**Files:**
- Create: `frontend/src/stores/auth.ts`
- Create: `frontend/src/stores/websocket.ts`

```typescript
// src/stores/auth.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, LoginCredentials } from '@/types';
import { authApi } from '@/api/auth';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null, token: null, isAuthenticated: false, isLoading: false,
      login: async (credentials) => {
        set({ isLoading: true });
        try {
          const response = await authApi.login(credentials);
          const user: User = {
            id: response.user_id,
            username: response.username,
            full_name: response.full_name,
            is_admin: response.is_admin,
          };
          set({ user, token: response.access_token, isAuthenticated: true, isLoading: false });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },
      logout: () => set({ user: null, token: null, isAuthenticated: false }),
    }),
    { name: 'auth-storage', partialize: (state) => ({ token: state.token, user: state.user, isAuthenticated: state.isAuthenticated }) }
  )
);
```

```typescript
// src/stores/websocket.ts
import { create } from 'zustand';
import type { WebSocketMessage } from '@/types';

interface WebSocketState {
  isConnected: boolean;
  lastMessage: WebSocketMessage | null;
  connect: (clientId: string) => void;
  disconnect: () => void;
}

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

export const useWebSocketStore = create<WebSocketState>((set, get) => ({
  isConnected: false,
  lastMessage: null,
  connect: (clientId: string) => {
    if (ws?.readyState === WebSocket.OPEN) return;
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/ws/${clientId}`;
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      set({ isConnected: true });
      setInterval(() => ws?.send(JSON.stringify({ type: 'ping' })), 30000);
    };
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WebSocketMessage;
        set({ lastMessage: message });
      } catch {}
    };
    ws.onclose = () => {
      set({ isConnected: false });
      reconnectTimer = setTimeout(() => get().connect(clientId), 3000);
    };
  },
  disconnect: () => {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    ws?.close();
    ws = null;
    set({ isConnected: false });
  },
}));
```

---

## Task 7: 创建自定义 Hooks

**Files:**
- Create: `frontend/src/hooks/useChat.ts`
- Create: `frontend/src/hooks/useTasks.ts`

```typescript
// src/hooks/useChat.ts
import { useState, useCallback, useRef } from 'react';
import { useAuthStore } from '@/stores/auth';
import { chatApi } from '@/api/chat';
import type { Message, SessionStatus } from '@/types';
import { toast } from '@/components/ui/use-toast';

export function useChat() {
  const { token } = useAuthStore();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const threadIdRef = useRef<string>(`web_${Date.now()}`);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!token || !content.trim()) return;
      const userMessage: Message = { id: Date.now().toString(), role: 'user', content, timestamp: new Date().toISOString() };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      let assistantContent = '';
      try {
        for await (const token_chunk of chatApi.streamChat({ question: content, thread_id: threadIdRef.current }, token)) {
          assistantContent += token_chunk;
          setMessages((prev) => {
            const newMessages = [...prev];
            const lastMsg = newMessages[newMessages.length - 1];
            if (lastMsg?.role === 'assistant') lastMsg.content = assistantContent;
            else newMessages.push({ id: (Date.now() + 1).toString(), role: 'assistant', content: assistantContent, timestamp: new Date().toISOString() });
            return [...newMessages];
          });
        }
        const sessionStatus = await chatApi.getStatus(threadIdRef.current);
        setStatus(sessionStatus);
      } catch (error) {
        toast({ title: '发送失败', description: error instanceof Error ? error.message : '未知错误', variant: 'destructive' });
      } finally {
        setIsLoading(false);
      }
    }, [token]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    threadIdRef.current = `web_${Date.now()}`;
    setStatus(null);
  }, []);

  return { messages, isLoading, status, sendMessage, clearMessages, threadId: threadIdRef.current };
}
```

```typescript
// src/hooks/useTasks.ts
import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '@/api/admin';
import type { Task, TaskFilters } from '@/types';
import { toast } from '@/components/ui/use-toast';

export function useTasks() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<TaskFilters>({ riskLevel: 'ALL' });
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ['tasks', filters],
    queryFn: () => adminApi.getTasks(filters.riskLevel),
    refetchInterval: 10000,
  });

  const decisionMutation = useMutation({
    mutationFn: ({ auditLogId, action, comment }: { auditLogId: number; action: 'APPROVE' | 'REJECT'; comment: string }) =>
      adminApi.makeDecision(auditLogId, { action, admin_comment: comment }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      setSelectedTask(null);
      toast({ title: '决策已提交', description: '任务状态已更新' });
    },
    onError: (error) => {
      toast({ title: '提交失败', description: error instanceof Error ? error.message : '未知错误', variant: 'destructive' });
    },
  });

  const makeDecision = useCallback(
    (auditLogId: number, action: 'APPROVE' | 'REJECT', comment: string) => decisionMutation.mutate({ auditLogId, action, comment }),
    [decisionMutation]
  );

  return { tasks, isLoading, filters, setFilters, selectedTask, setSelectedTask, makeDecision, isSubmitting: decisionMutation.isPending };
}
```

---

## Task 8: C 端实现

### 8.1 路由配置

```typescript
// src/apps/customer/routes.tsx
import { Suspense, lazy } from 'react';
import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '@/stores/auth';

const Login = lazy(() => import('./pages/Login'));
const Chat = lazy(() => import('./pages/Chat'));

const PageLoader = () => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="animate-spin h-8 w-8 border-4 border-brand-500 border-t-transparent rounded-full" />
  </div>
);

const ProtectedRoute = () => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
};

export const router = createBrowserRouter([
  { path: '/login', element: (<Suspense fallback={<PageLoader />}><Login /></Suspense>) },
  { element: <ProtectedRoute />, children: [{ path: '/chat', element: (<Suspense fallback={<PageLoader />}><Chat /></Suspense>) }] },
  { path: '/', element: <Navigate to="/chat" replace /> },
]);
```

### 8.2 C 端入口

```typescript
// src/apps/customer/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/query-client';
import { router } from './routes';
import { Toaster } from '@/components/ui/toaster';
import '../../styles/globals.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster />
    </QueryClientProvider>
  </React.StrictMode>
);
```

### 8.3 C 端登录页

```typescript
// src/apps/customer/pages/Login.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Loader2 } from 'lucide-react';

export function Login() {
  const navigate = useNavigate();
  const { login, isLoading } = useAuthStore();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;
    try {
      await login({ username, password });
      navigate('/chat');
    } catch {}
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="text-center">
          <div className="text-4xl mb-2">🤖</div>
          <CardTitle className="text-2xl">欢迎登录</CardTitle>
          <CardDescription>E-commerce Smart Agent v4.0</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">账号</label>
              <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="请输入用户名" disabled={isLoading} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">密码</label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="请输入密码" disabled={isLoading} />
            </div>
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />登录中...</>) : '立即登录'}
            </Button>
          </form>
          <Accordion type="single" collapsible className="mt-4">
            <AccordionItem value="test-accounts">
              <AccordionTrigger className="text-sm text-gray-500">点击查看测试账号</AccordionTrigger>
              <AccordionContent>
                <div className="text-sm space-y-2 text-gray-600">
                  <div className="grid grid-cols-3 gap-2 font-medium border-b pb-2"><span>用户</span><span>账号/密码</span><span>订单</span></div>
                  <div className="grid grid-cols-3 gap-2"><span>Alice</span><span className="font-mono">alice / alice123</span><span>SN20240001-003</span></div>
                  <div className="grid grid-cols-3 gap-2"><span>Bob</span><span className="font-mono">bob / bob123</span><span>SN20240004-005</span></div>
                  <div className="grid grid-cols-3 gap-2"><span>Admin</span><span className="font-mono">admin / admin123</span><span>管理员</span></div>
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </CardContent>
      </Card>
    </div>
  );
}
```

### 8.4 C 端聊天页

```typescript
// src/apps/customer/pages/Chat.tsx
import { useAuthStore } from '@/stores/auth';
import { useChat } from '@/hooks/useChat';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { LogOut } from 'lucide-react';
import { ChatMessage } from '../components/ChatMessage';
import { ChatInput } from '../components/ChatInput';
import { QuickActions } from '../components/QuickActions';

export function Chat() {
  const { user, logout } = useAuthStore();
  const { messages, isLoading, status, sendMessage } = useChat();

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl">🏠</span>
          <h1 className="font-semibold text-lg">Smart Agent</h1>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-600">👤 {user?.full_name} (ID: {user?.id})</span>
          <Button variant="outline" size="sm" onClick={logout}><LogOut className="h-4 w-4 mr-1" />退出</Button>
        </div>
      </header>
      <ScrollArea className="flex-1 p-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <span className="text-4xl mb-4">🤖</span>
            <h2 className="text-xl font-semibold mb-2">我是您的智能客服助手</h2>
            <p className="text-gray-600">我可以帮您查询订单、了解退货政策、提交退货申请</p>
          </div>
        ) : (
          <div className="space-y-4 max-w-3xl mx-auto">
            {messages.map((message) => <ChatMessage key={message.id} message={message} status={status} />)}
          </div>
        )}
      </ScrollArea>
      <QuickActions onSelect={sendMessage} />
      <ChatInput onSend={sendMessage} isLoading={isLoading} />
    </div>
  );
}
```

### 8.5 C 端组件

```typescript
// src/apps/customer/components/ChatMessage.tsx
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Card } from '@/components/ui/card';
import type { Message, SessionStatus } from '@/types';

interface ChatMessageProps { message: Message; status: SessionStatus | null; }

export function ChatMessage({ message, status }: ChatMessageProps) {
  const isUser = message.role === 'user';
  return (
    <div className="flex gap-3">
      {!isUser && (<Avatar className="h-8 w-8"><AvatarFallback className="bg-brand-100 text-brand-600">🤖</AvatarFallback></Avatar>)}
      <div className="flex-1">
        <Card className={`p-3 ${isUser ? 'bg-gray-100 ml-auto max-w-[80%]' : 'bg-white border-l-4 border-l-brand-500 max-w-[90%]'}`}>
          <div className="whitespace-pre-wrap text-sm">{message.content}</div>
        </Card>
        {!isUser && status?.status === 'WAITING_ADMIN' && (
          <div className="mt-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm">
            <div className="font-medium text-yellow-800">⏳ 触发风控审核</div>
            <div className="text-yellow-700">原因：{status.data?.trigger_reason}<br/>风险等级：{status.data?.risk_level}</div>
          </div>
        )}
      </div>
    </div>
  );
}
```

```typescript
// src/apps/customer/components/ChatInput.tsx
import { useState, useRef, KeyboardEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Send } from 'lucide-react';

interface ChatInputProps { onSend: (message: string) => void; isLoading: boolean; }

export function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const handleSend = () => { if (!input.trim() || isLoading) return; onSend(input); setInput(''); inputRef.current?.focus(); };
  const handleKeyDown = (e: KeyboardEvent) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } };
  return (
    <div className="bg-white border-t p-4">
      <div className="flex gap-2 max-w-3xl mx-auto">
        <Input ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="请输入消息... (Enter 发送)" disabled={isLoading} className="flex-1" />
        <Button onClick={handleSend} disabled={isLoading || !input.trim()}>{isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}</Button>
      </div>
    </div>
  );
}
```

```typescript
// src/apps/customer/components/QuickActions.tsx
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface QuickActionsProps { onSelect: (message: string) => void; }

const actions = [
  { category: '订单查询', items: [{ label: '我的订单', message: '查询我的订单' }, { label: 'Alice 的订单', message: '查询订单 SN20240001' }, { label: 'Bob 的订单', message: '查询订单 SN20240004' }] },
  { category: '售后服务', items: [{ label: '退货政策', message: '内衣可以退货吗？' }, { label: '模拟退货', message: '我要退货，订单号 SN20240003，尺码不合适' }, { label: '大额退款', message: '我要退款 2500 元，订单 SN20240003，质量有问题' }] },
];

export function QuickActions({ onSelect }: QuickActionsProps) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div className="bg-white border-t px-4 py-2">
      <button onClick={() => setIsOpen(!isOpen)} className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900">
        {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}快捷工具
      </button>
      {isOpen && (
        <div className="mt-2 flex flex-wrap gap-2">
          {actions.map((group) => (
            <div key={group.category} className="flex items-center gap-2">
              <span className="text-xs text-gray-500">{group.category}:</span>
              {group.items.map((item) => <Button key={item.label} variant="outline" size="sm" onClick={() => onSelect(item.message)}>{item.label}</Button>)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

---

## Task 9: B 端实现

### 9.1 B 端路由

```typescript
// src/apps/admin/routes.tsx
import { Suspense, lazy } from 'react';
import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '@/stores/auth';

const Login = lazy(() => import('./pages/Login'));
const Dashboard = lazy(() => import('./pages/Dashboard'));

const PageLoader = () => (<div className="flex items-center justify-center min-h-screen"><div className="animate-spin h-8 w-8 border-4 border-brand-500 border-t-transparent rounded-full" /></div>);

const AdminRoute = () => {
  const { isAuthenticated, user } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!user?.is_admin) return <Navigate to="/" replace />;
  return <Outlet />;
};

export const router = createBrowserRouter([
  { path: '/login', element: (<Suspense fallback={<PageLoader />}><Login /></Suspense>) },
  { element: <AdminRoute />, children: [{ path: '/dashboard', element: (<Suspense fallback={<PageLoader />}><Dashboard /></Suspense>) }] },
  { path: '/', element: <Navigate to="/dashboard" replace /> },
]);
```

### 9.2 B 端入口

```typescript
// src/apps/admin/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/query-client';
import { router } from './routes';
import { Toaster } from '@/components/ui/toaster';
import '../../styles/globals.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster />
    </QueryClientProvider>
  </React.StrictMode>
);
```

### 9.3 B 端登录页

```typescript
// src/apps/admin/pages/Login.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';

export function Login() {
  const navigate = useNavigate();
  const { login, isLoading } = useAuthStore();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;
    try { await login({ username, password }); navigate('/dashboard'); } catch {}
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="text-center">
          <div className="text-4xl mb-2">🛡️</div>
          <CardTitle className="text-2xl">管理员登录</CardTitle>
          <CardDescription>Admin Dashboard v4.0</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">账号</label>
              <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="请输入管理员账号" disabled={isLoading} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">密码</label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="请输入密码" disabled={isLoading} />
            </div>
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />登录中...</>) : '登录'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

### 9.4 Dashboard 和三栏布局

```typescript
// src/apps/admin/pages/Dashboard.tsx
import { useEffect } from 'react';
import { useAuthStore } from '@/stores/auth';
import { useWebSocketStore } from '@/stores/websocket';
import { useTasks } from '@/hooks/useTasks';
import { Button } from '@/components/ui/button';
import { LogOut } from 'lucide-react';
import { TaskList } from '../components/TaskList';
import { TaskDetail } from '../components/TaskDetail';
import { DecisionPanel } from '../components/DecisionPanel';

export function Dashboard() {
  const { user, logout } = useAuthStore();
  const { connect, disconnect, lastMessage } = useWebSocketStore();
  const { tasks, isLoading, filters, setFilters, selectedTask, setSelectedTask, makeDecision, isSubmitting } = useTasks();

  useEffect(() => { if (user) { connect(`admin_${user.id}`); return () => disconnect(); } }, [user, connect, disconnect]);

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      <header className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2"><span className="text-xl">🛡️</span><h1 className="font-semibold text-lg">Admin Dashboard</h1></div>
        <div className="flex items-center gap-4"><span className="text-sm text-gray-600">👤 {user?.username}</span><Button variant="outline" size="sm" onClick={logout}><LogOut className="h-4 w-4 mr-1" />退出</Button></div>
      </header>
      <div className="flex-1 grid grid-cols-[280px_1fr_320px] gap-4 p-4 overflow-hidden">
        <TaskList tasks={tasks} isLoading={isLoading} filters={filters} onFilterChange={setFilters} selectedTask={selectedTask} onSelectTask={setSelectedTask} />
        <TaskDetail task={selectedTask} />
        <DecisionPanel task={selectedTask} onDecision={makeDecision} isSubmitting={isSubmitting} />
      </div>
    </div>
  );
}
```

### 9.5 B 端组件

```typescript
// src/apps/admin/components/TaskList.tsx
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import type { Task, TaskFilters } from '@/types';

interface TaskListProps { tasks: Task[]; isLoading: boolean; filters: TaskFilters; onFilterChange: (filters: TaskFilters) => void; selectedTask: Task | null; onSelectTask: (task: Task) => void; }

export function TaskList({ tasks, isLoading, filters, onFilterChange, selectedTask, onSelectTask }: TaskListProps) {
  const getRiskColor = (risk: string) => { switch(risk) { case 'HIGH': return 'bg-red-100 text-red-700'; case 'MEDIUM': return 'bg-yellow-100 text-yellow-700'; case 'LOW': return 'bg-green-100 text-green-700'; default: return 'bg-gray-100'; } };
  return (
    <div className="bg-white rounded-lg border flex flex-col">
      <div className="p-3 border-b"><h2 className="font-semibold">任务队列</h2><div className="text-sm text-gray-500">待审核: {tasks.length}</div></div>
      <div className="p-3 border-b">
        <RadioGroup value={filters.riskLevel} onValueChange={(v) => onFilterChange({ riskLevel: v as TaskFilters['riskLevel'] })} className="flex gap-2">
          {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map((level) => (<div key={level} className="flex items-center space-x-1"><RadioGroupItem value={level} id={level} /><Label htmlFor={level} className="text-xs">{level === 'ALL' ? '全部' : level}</Label></div>))}
        </RadioGroup>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-2">
          {isLoading ? Array.from({ length: 5 }).map((_, i) => (<div key={i} className="p-3 border rounded"><Skeleton className="h-4 w-20 mb-2" /><Skeleton className="h-3 w-full" /></div>)) :
           tasks.length === 0 ? <div className="p-4 text-center text-gray-500 text-sm">暂无待审核任务</div> :
           tasks.map((task) => (<div key={task.audit_log_id} onClick={() => onSelectTask(task)} className={`p-3 border rounded cursor-pointer hover:bg-gray-50 ${selectedTask?.audit_log_id === task.audit_log_id ? 'border-brand-500 bg-brand-50' : ''}`}><div className="flex justify-between items-start"><span className="font-medium text-sm">#{task.audit_log_id}</span><Badge className={getRiskColor(task.risk_level)}>{task.risk_level}</Badge></div><div className="text-sm text-gray-600 mt-1">用户: {task.user_id}</div><div className="text-xs text-gray-400 mt-1">{new Date(task.created_at).toLocaleString()}</div></div>))}
        </div>
      </ScrollArea>
    </div>
  );
}
```

```typescript
// src/apps/admin/components/TaskDetail.tsx
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card } from '@/components/ui/card';
import type { Task } from '@/types';

interface TaskDetailProps { task: Task | null; }

export function TaskDetail({ task }: TaskDetailProps) {
  if (!task) return (<div className="bg-white rounded-lg border flex items-center justify-center"><div className="text-gray-400">请从左侧选择任务</div></div>);
  const orderData = task.context_snapshot?.order_data;
  return (
    <div className="bg-white rounded-lg border flex flex-col">
      <div className="p-3 border-b"><h2 className="font-semibold">任务 #{task.audit_log_id}</h2></div>
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          <div><h3 className="text-sm font-medium text-gray-500 mb-1">用户问题</h3><Card className="p-3 bg-gray-50">{task.context_snapshot?.question || '无'}</Card></div>
          <div><h3 className="text-sm font-medium text-gray-500 mb-1">触发原因</h3><Card className="p-3 bg-yellow-50 border-yellow-200">{task.trigger_reason}</Card></div>
          {orderData && (<div><h3 className="text-sm font-medium text-gray-500 mb-1">订单信息</h3><Card className="p-3 border-l-4 border-l-brand-500"><div className="flex justify-between"><span className="font-medium">{orderData.order_sn}</span><span className="text-red-500 font-bold">¥{orderData.total_amount}</span></div><div className="text-sm text-gray-600 mt-1">{orderData.status}</div><div className="mt-2 space-y-1">{orderData.items.map((item, i) => (<div key={i} className="text-sm text-gray-600">{item.name} x {item.qty}</div>))}</div></Card></div>)}
          <div><h3 className="text-sm font-medium text-gray-500 mb-1">完整上下文</h3><pre className="text-xs bg-gray-100 p-2 rounded overflow-auto max-h-40">{JSON.stringify(task.context_snapshot, null, 2)}</pre></div>
        </div>
      </ScrollArea>
    </div>
  );
}
```

```typescript
// src/apps/admin/components/DecisionPanel.tsx
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import type { Task } from '@/types';

interface DecisionPanelProps { task: Task | null; onDecision: (auditLogId: number, action: 'APPROVE' | 'REJECT', comment: string) => void; isSubmitting: boolean; }

export function DecisionPanel({ task, onDecision, isSubmitting }: DecisionPanelProps) {
  const [comment, setComment] = useState('');
  if (!task) return (<div className="bg-white rounded-lg border flex items-center justify-center"><div className="text-gray-400">请先选择任务</div></div>);
  const getRiskBadge = (risk: string) => { switch(risk) { case 'HIGH': return <Badge className="bg-red-100 text-red-700">高风险</Badge>; case 'MEDIUM': return <Badge className="bg-yellow-100 text-yellow-700">中风险</Badge>; case 'LOW': return <Badge className="bg-green-100 text-green-700">低风险</Badge>; default: return <Badge>未知</Badge>; } };
  const handleApprove = () => { onDecision(task.audit_log_id, 'APPROVE', comment); setComment(''); };
  const handleReject = () => { if (!comment.trim()) { alert('拒绝时必须填写审核备注'); return; } onDecision(task.audit_log_id, 'REJECT', comment); setComment(''); };
  return (
    <div className="bg-white rounded-lg border flex flex-col">
      <div className="p-3 border-b"><h2 className="font-semibold">决策面板</h2></div>
      <div className="p-4 space-y-4">
        <div className="flex items-center justify-between"><span className="text-sm text-gray-600">风险等级</span>{getRiskBadge(task.risk_level)}</div>
        <div><label className="text-sm font-medium">审核备注</label><Textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="请输入审核意见（拒绝时必填）" rows={4} className="mt-1" /></div>
        <div className="space-y-2">
          <Button onClick={handleApprove} disabled={isSubmitting} className="w-full bg-green-600 hover:bg-green-700">{isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : '✓ 批准'}</Button>
          <Button onClick={handleReject} disabled={isSubmitting} variant="destructive" className="w-full">{isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : '✗ 拒绝'}</Button>
        </div>
        <Card className="p-3 bg-gray-50"><div className="text-xs text-gray-500 space-y-1"><div>管理员ID: {task.user_id}</div><div>API状态: 已连接</div></div></Card>
      </div>
    </div>
  );
}
```

---

## Task 10: FastAPI 静态文件托管

**Modify:** `app/main.py`

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
import os

# 在路由注册后添加
frontend_dist_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')

if os.path.exists(frontend_dist_path):
    @app.get('/app/{full_path:path}')
    async def serve_customer_spa(full_path: str):
        return FileResponse(os.path.join(frontend_dist_path, 'customer', 'index.html'))

    app.mount('/app', StaticFiles(directory=os.path.join(frontend_dist_path, 'customer'), html=True), name='customer_app')

    @app.get('/admin/{full_path:path}')
    async def serve_admin_spa(full_path: str):
        return FileResponse(os.path.join(frontend_dist_path, 'admin', 'index.html'))

    app.mount('/admin', StaticFiles(directory=os.path.join(frontend_dist_path, 'admin'), html=True), name='admin_app')

    @app.get('/')
    async def root():
        return RedirectResponse(url='/app')
```

---

## 执行检查清单

| 阶段 | 检查命令 | 预期结果 |
|------|---------|---------|
| 依赖安装 | `ls frontend/node_modules` | 目录存在 |
| 开发服务器 | `npm run dev` | localhost:5173 可访问 |
| TypeScript | `npx tsc --noEmit` | 无错误 |
| 生产构建 | `npm run build` | dist/ 目录生成 |
| 后端托管 | `uvicorn app.main:app` | /app 和 /admin 可访问 |

---

**版本**: 2.0
**更新日期**: 2025-04-08
