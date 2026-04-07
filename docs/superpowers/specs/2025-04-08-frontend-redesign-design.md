# E-commerce Smart Agent 前端重构设计文档

**日期**: 2025-04-08
**状态**: 待实施
**架构方案**: 嵌入式架构（方案二）

---

## 1. 项目概述

### 1.1 目标
将现有的 Gradio 前端重构为 React + Tailwind CSS 现代前端，提升用户体验和视觉品质。

### 1.2 设计原则
- **简约现代**: 参考 Notion、Linear、Vercel 的设计风格
- **高效专注**: B 端三栏布局，信息密度高
- **实时响应**: WebSocket 实时推送，Toast 通知
- **类型安全**: TypeScript 全栈类型支持

### 1.3 技术栈
| 层级 | 技术 |
|------|------|
| 框架 | React 18 + TypeScript |
| 构建 | Vite |
| 样式 | Tailwind CSS |
| 组件 | shadcn/ui |
| 状态 | Zustand |
| 数据获取 | TanStack Query |
| 路由 | React Router v6 |

---

## 2. 架构设计

### 2.1 项目结构

```
E-commerce-Smart-Agent/
├── app/                        # Python FastAPI 后端
│   ├── api/v1/
│   ├── core/
│   ├── models/
│   ├── services/
│   ├── websocket/
│   └── main.py
│
├── frontend/                   # React + Vite 前端
│   ├── src/
│   │   ├── apps/
│   │   │   ├── customer/       # C端用户界面
│   │   │   │   ├── pages/
│   │   │   │   │   ├── Login.tsx
│   │   │   │   │   └── Chat.tsx
│   │   │   │   ├── components/
│   │   │   │   ├── hooks/
│   │   │   │   └── main.tsx
│   │   │   │
│   │   │   └── admin/          # B端管理后台
│   │   │       ├── pages/
│   │   │       │   ├── Login.tsx
│   │   │       │   └── Dashboard.tsx
│   │   │       ├── components/
│   │   │       │   ├── TaskList.tsx
│   │   │       │   ├── TaskDetail.tsx
│   │   │       │   └── DecisionPanel.tsx
│   │   │       ├── hooks/
│   │   │       └── main.tsx
│   │   │
│   │   ├── components/         # 共享组件
│   │   │   ├── ui/             # shadcn/ui 基础组件
│   │   │   └── common/         # 业务共享组件
│   │   ├── hooks/              # 共享 hooks
│   │   ├── lib/                # 工具函数
│   │   ├── api/                # API 客户端
│   │   ├── types/              # TypeScript 类型
│   │   └── styles/             # 全局样式
│   │
│   ├── index.html              # C端入口
│   ├── admin.html              # B端入口
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── package.json
│
├── package.json                # 根目录脚本
└── README.md
```

### 2.2 部署策略

**开发阶段:**
- Vite dev server: C端 5173, B端 5174
- FastAPI: 8000
- CORS 配置允许跨域

**生产阶段:**
- 前端构建为静态文件
- FastAPI `StaticFiles` 托管
- 单域名部署，无跨域

```python
# app/main.py 添加
from fastapi.staticfiles import StaticFiles

app.mount("/app", StaticFiles(directory="frontend/dist/app"), name="customer")
app.mount("/admin", StaticFiles(directory="frontend/dist/admin"), name="admin")
```

### 2.3 Vite 多页面配置

**index.html** (C端入口):
```html
<!DOCTYPE html>
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

**admin.html** (B端入口):
```html
<!DOCTYPE html>
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

**vite.config.ts**:
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

---

## 3. C 端用户界面设计

### 3.1 布局风格
**左对齐统一布局**（Notion AI/ChatGPT 风格）
- 所有消息左对齐
- 用户头像在输入框处显示
- 输入框固定在底部

### 3.2 页面结构

#### 登录页
```
┌─────────────────────────────────────────┐
│                                         │
│           [品牌 Logo]                   │
│                                         │
│           欢迎登录                       │
│      E-commerce Smart Agent v4.0        │
│                                         │
│    ┌─────────────────────────────┐      │
│    │ 账号                        │      │
│    │ [____________________]      │      │
│    └─────────────────────────────┘      │
│    ┌─────────────────────────────┐      │
│    │ 密码                        │      │
│    │ [____________________]      │      │
│    └─────────────────────────────┘      │
│                                         │
│         [ 立即登录 ]                    │
│                                         │
│    [测试账号 ▼]                         │
│                                         │
└─────────────────────────────────────────┘
```

#### 聊天界面
```
┌─────────────────────────────────────────────────┐
│  🏠 Smart Agent                          👤 Alice │  ← 顶部导航
├─────────────────────────────────────────────────┤
│                                                 │
│  🤖 你好！有什么可以帮您的吗？                      │
│                                                 │
│  ┌─────────────────────────────────────────┐    │
│  │ 👤 查询我的订单                          │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  🤖 为您查询到以下订单：                          │
│                                                 │
│     ┌─────────────────────────────────────┐     │
│     │  📦 SN20240001                       │     │
│     │     ¥299  |  已发货                   │     │
│     └─────────────────────────────────────┘     │
│                                                 │
│     ┌─────────────────────────────────────┐     │
│     │  📦 SN20240002                       │     │
│     │     ¥599  |  待发货                   │     │
│     └─────────────────────────────────────┘     │
│                                                 │
├─────────────────────────────────────────────────┤
│  [输入消息...                    ] [➤]         │  ← 输入区
│  [⏳ 等待审核中...]                              │  ← 状态栏
└─────────────────────────────────────────────────┘
```

### 3.3 消息样式

| 元素 | 样式 |
|------|------|
| AI 消息 | 白色背景，左边 3px 品牌色竖条，圆角 12px |
| 用户消息 | 浅灰背景 `#f3f4f6`，圆角 12px |
| 订单卡片 | 白色背景，轻微阴影，hover 时边框变蓝 |
| 审核状态卡片 | 黄色边框（待审核）/ 绿色（通过）/ 红色（拒绝） |
| 时间戳 | 12px 灰色，右对齐 |

### 3.4 快捷工具箱

**位置调整**：从右侧悬浮改为**输入框上方可折叠面板**，避免遮挡聊天内容。

```
┌─────────────────────────────────────────────────┐
│  🤖 你好！有什么可以帮您的吗？                      │
│                                                 │
├─────────────────────────────────────────────────┤
│  [快捷工具 ▼]                                    │
│  ┌─────────────────────────────────────────┐    │
│  │ 订单查询: [我的订单] [Alice订单] [Bob订单] │    │
│  │ 售后服务: [退货政策] [模拟退货] [大额退款] │    │
│  └─────────────────────────────────────────┘    │
├─────────────────────────────────────────────────┤
│  [输入消息...                    ] [➤]         │
└─────────────────────────────────────────────────┘
```

**快捷按钮列表**：
- 📋 我的订单
- 📋 Alice 的订单（测试越权）
- 📋 Bob 的订单（测试越权）
- ───────
- 📖 退货政策
- 🔄 模拟退货
- ⚠️ 大额退款（触发风控）

---

## 4. B 端管理后台设计

### 4.1 布局风格
**三栏固定布局**（类似 Linear/GitHub Projects）

### 4.2 页面结构

```
┌─────────────────────────────────────────────────────────────────┐
│  🛡️ Admin Dashboard                                  👤 Admin   │  ← 顶部导航
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌─────────────────────────┐  ┌────────────────┐ │
│  │ 🔍 筛选   │  │ 任务 #42                 │  │ 决策面板        │ │
│  │          │  │ ───────────────────────  │  │                │ │
│  │ ○ 全部   │  │ 用户: Alice              │  │ 风险等级: HIGH │ │
│  │ ● HIGH 3 │  │ 金额: ¥2,500             │  │                │ │
│  │ ○ MED 1  │  │ 原因: 大额退款            │  │ ┌───────────┐  │ │
│  │ ○ LOW 5  │  │                          │  │ │ 审核备注   │  │ │
│  │          │  │ 上下文快照:               │  │ │ [         ]│  │ │
│  │ ──────── │  │ {...}                    │  │ │ [         ]│  │ │
│  │ 待审核: 9│  │                          │  │ └───────────┘  │ │
│  └──────────┘  │ 订单详情:                 │  │                │ │
│                │ ┌─────────────────────┐   │  │ [ ✓ 批准 ]   │ │
│                │ │ 📦 SN20240003        │   │  │              │ │
│                │ │ ¥2,500 | 待审核      │   │  │ [ ✗ 拒绝 ]   │ │
│                │ └─────────────────────┘   │  │              │ │
│                └─────────────────────────┘  │  └────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
│  [Toast: 新任务 #43 来自用户 Bob - ¥3,200]          [×]          │  ← Toast 通知
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 三栏布局尺寸

采用**固定 + 自适应**混合布局，确保可读性和操作空间：

| 栏位 | 宽度 | 最小宽度 | 说明 |
|------|------|---------|------|
| 左栏（任务列表） | 280px 固定 | 280px | 任务列表需要可读性 |
| 中栏（详情展示） | flex-1 自适应 | 500px | 上下文和订单详情 |
| 右栏（决策面板） | 320px 固定 | 320px | 决策面板需要足够宽度 |

```css
/* 布局实现 */
.admin-layout {
  display: grid;
  grid-template-columns: 280px 1fr 320px;
  gap: 16px;
  min-width: 1200px;
  padding: 16px;
}

/* 当屏幕宽度不足时显示提示 */
@media (max-width: 1200px) {
  .admin-layout {
    display: none;
  }
  .screen-too-small {
    display: flex;
  }
}
```

### 4.4 任务列表

| 列 | 内容 | 样式 |
|----|------|------|
| ID | #42 | 品牌色链接 |
| 用户 | Alice | 正常文字 |
| 风险 | HIGH | 红色徽章 |
| 金额 | ¥2,500 | 加粗 |
| 时间 | 2分钟前 | 灰色小字 |

**筛选器:**
- 风险等级: 全部 / HIGH / MEDIUM / LOW
- 刷新按钮

### 4.5 决策面板

**审核状态:**
- 风险等级徽章（红/黄/绿）
- 触发原因文本

**操作区:**
- 审核备注输入框（拒绝时必填）
- 批准按钮（主色）
- 拒绝按钮（红色危险样式）

**系统信息:**
- 管理员 ID
- API 连接状态

### 4.6 实时通知

**Toast 通知样式:**
```
┌──────────────────────────────────────────────┐
│ 🔔 新任务                                     │
│ 用户 Bob 提交了大额退款申请                   │
│ ¥3,200 · HIGH 风险 · 刚刚                    │
└──────────────────────────────────────────────┘
```

**通知类型:**
- 新任务到达（蓝色边框）
- 审核完成（绿色边框）
- 系统错误（红色边框）

**行为:**
- 右上角滑入
- 3秒后自动消失
- 可手动关闭
- 点击 Toast 定位到对应任务

---

## 5. 设计系统

### 5.1 颜色系统

```typescript
// tailwind.config.ts
colors: {
  // 品牌色 - 靛蓝
  brand: {
    50: '#eff6ff',
    100: '#dbeafe',
    200: '#bfdbfe',
    300: '#93c5fd',
    400: '#60a5fa',
    500: '#3b82f6',  // 主色
    600: '#2563eb',
    700: '#1d4ed8',
    800: '#1e40af',
    900: '#1e3a8a',
  },

  // 语义色
  success: {
    50: '#f0fdf4',
    100: '#dcfce7',
    500: '#22c55e',
    600: '#16a34a',
  },
  warning: {
    50: '#fffbeb',
    100: '#fef3c7',
    500: '#f59e0b',
    600: '#d97706',
  },
  danger: {
    50: '#fef2f2',
    100: '#fee2e2',
    500: '#ef4444',
    600: '#dc2626',
  },

  // 中性色
  gray: {
    50: '#f9fafb',   // 页面背景
    100: '#f3f4f6',  // 卡片背景/用户消息
    200: '#e5e7eb',  // 边框
    300: '#d1d5db',  // 禁用
    400: '#9ca3af',  // 次要文字
    500: '#6b7280',  // 辅助文字
    600: '#4b5563',  // 正文
    700: '#374151',  // 次级标题
    800: '#1f2937',  // 标题
    900: '#111827',  // 主标题
  }
}
```

### 5.2 字体系统

```typescript
fontFamily: {
  sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
}

fontSize: {
  xs: ['0.75rem', { lineHeight: '1rem' }],      // 12px - 辅助文字
  sm: ['0.875rem', { lineHeight: '1.25rem' }],  // 14px - 正文
  base: ['1rem', { lineHeight: '1.5rem' }],     // 16px - 默认
  lg: ['1.125rem', { lineHeight: '1.75rem' }],  // 18px - 小标题
  xl: ['1.25rem', { lineHeight: '1.75rem' }],   // 20px - 标题
  '2xl': ['1.5rem', { lineHeight: '2rem' }],    // 24px - 大标题
}
```

### 5.3 间距系统

使用 Tailwind 默认间距即可：
- 页面内边距: `p-6` (24px)
- 卡片内边距: `p-4` (16px)
- 元素间距: `gap-4` (16px)
- 小组件间距: `gap-2` (8px)

### 5.4 圆角系统

```typescript
borderRadius: {
  sm: '0.25rem',   // 4px - 小按钮
  DEFAULT: '0.5rem', // 8px - 输入框
  md: '0.5rem',    // 8px
  lg: '0.75rem',   // 12px - 卡片
  xl: '1rem',      // 16px - 大卡片
  '2xl': '1.5rem', // 24px - 模态框
  full: '9999px',  // 全圆角 - 徽章
}
```

### 5.5 阴影系统

```typescript
boxShadow: {
  sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
  DEFAULT: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  md: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
  lg: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
}
```

---

## 6. 组件清单

### 6.1 shadcn/ui 基础组件

| 组件 | 用途 |
|------|------|
| Button | 所有按钮 |
| Input | 输入框 |
| Textarea | 多行输入 |
| Card | 卡片容器 |
| Badge | 状态徽章 |
| Dialog | 模态框 |
| DropdownMenu | 下拉菜单 |
| Tabs | 标签页 |
| ScrollArea | 滚动区域 |
| Separator | 分隔线 |
| Skeleton | 加载骨架 |
| Toast | 通知提示 |
| Tooltip | 工具提示 |
| Avatar | 头像 |
| Select | 下拉选择 |
| Checkbox | 复选框 |
| RadioGroup | 单选组 |
| Accordion | 折叠面板 |

### 6.2 业务组件

**C端:**
- `ChatMessage` - 消息气泡
- `OrderCard` - 订单信息卡片
- `AuditStatusCard` - 审核状态卡片
- `QuickActions` - 快捷工具面板
- `ChatInput` - 聊天输入框

**B端:**
- `TaskList` - 任务列表
- `TaskListItem` - 任务列表项
- `TaskDetail` - 任务详情
- `DecisionPanel` - 决策面板
- `ContextViewer` - 上下文展示
- `OrderViewer` - 订单信息展示
- `RiskBadge` - 风险等级徽章
- `RealtimeToast` - 实时通知 Toast

---

## 7. 状态管理

### 7.1 Zustand Stores

```typescript
// stores/auth.ts
interface AuthStore {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
}

// stores/chat.ts (C端)
interface ChatStore {
  messages: Message[];
  threadId: string;
  status: 'idle' | 'loading' | 'waiting_admin' | 'error';
  sendMessage: (content: string) => Promise<void>;
  clearMessages: () => void;
}

// stores/tasks.ts (B端)
interface TaskStore {
  tasks: Task[];
  selectedTask: Task | null;
  filters: {
    riskLevel: 'ALL' | 'HIGH' | 'MEDIUM' | 'LOW';
  };
  isLoading: boolean;
  fetchTasks: () => Promise<void>;
  selectTask: (taskId: number) => void;
  makeDecision: (taskId: number, action: 'APPROVE' | 'REJECT', comment: string) => Promise<void>;
}

// stores/websocket.ts
interface WebSocketStore {
  isConnected: boolean;
  connect: () => void;
  disconnect: () => void;
  sendMessage: (message: WebSocketMessage) => void;
}
```

### 7.2 状态管理分工

| 数据类型 | 管理方式 | 示例 | 说明 |
|---------|---------|------|------|
| **服务端状态** | TanStack Query | 任务列表、消息历史、订单数据 | 需要缓存、重新获取、乐观更新 |
| **客户端全局状态** | Zustand | 当前用户、选中任务、WebSocket连接 | 应用级共享状态 |
| **局部状态** | useState/useReducer | 表单输入、展开/折叠、弹窗开关 | 组件内部状态 |
| **URL状态** | React Router | 筛选条件、分页参数 | 可分享、可刷新的状态 |

### 7.3 TanStack Query 使用规范

```typescript
// 查询任务列表
const { data: tasks, isLoading, error } = useQuery({
  queryKey: ['tasks', filters],
  queryFn: () => api.getTasks(filters),
  refetchInterval: 30000, // 30秒自动刷新
  staleTime: 10000, // 10秒内不重复请求
});

// 提交决策（乐观更新）
const mutation = useMutation({
  mutationFn: ({ taskId, action, comment }) =>
    api.makeDecision(taskId, action, comment),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['tasks'] });
    toast.success('决策已提交');
  },
});
```

---

## 8. API 设计

### 8.1 接口列表

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/login` | 用户登录 |
| POST | `/api/v1/chat` | 发送消息（SSE 流式）|
| GET | `/api/v1/status/{thread_id}` | 查询会话状态 |
| GET | `/api/v1/admin/tasks` | 获取待审核任务 |
| POST | `/api/v1/admin/resume/{audit_log_id}` | 提交审核决策 |
| WS | `/api/v1/ws/{client_id}` | WebSocket 连接 |

### 8.2 SSE 流式响应处理

C 端聊天使用 Server-Sent Events (SSE) 实现流式输出：

```typescript
// api/chat.ts
async function* streamChat(
  question: string,
  threadId: string,
  token: string
): AsyncGenerator<string, void, unknown> {
  const response = await fetch('/api/v1/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ question, thread_id: threadId }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

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
          } catch {
            // 忽略解析错误，继续接收
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// 在组件中使用
const handleSendMessage = async (content: string) => {
  addMessage({ role: 'user', content });

  let assistantMessage = '';
  for await (const token of streamChat(content, threadId, token)) {
    assistantMessage += token;
    updateLastMessage({ role: 'assistant', content: assistantMessage });
  }

  // 流式接收完成后，查询最终状态
  const status = await fetchStatus(threadId);
  updateMessageStatus(status);
};
```

### 8.3 类型定义

```typescript
// types/index.ts

export interface User {
  id: number;
  username: string;
  full_name: string;
  is_admin: boolean;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
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

export interface ContextSnapshot {
  question: string;
  order_data?: Order;
}

export interface Order {
  order_sn: string;
  total_amount: number;
  status: string;
  items: OrderItem[];
}

export interface OrderItem {
  name: string;
  qty: number;
}
```

---

## 9. 错误处理策略

### 9.1 错误分类与处理

| 错误类型 | 场景 | 处理方式 | UI 反馈 |
|---------|------|----------|---------|
| **401 Unauthorized** | Token 过期、未登录 | 清除登录态，跳转登录页 | 提示「登录已过期，请重新登录」 |
| **403 Forbidden** | 权限不足 | 提示无权限，记录日志 | Toast 提示「无权限执行此操作」 |
| **404 Not Found** | 资源不存在 | 显示 404 页面 | 友好错误页 |
| **500 Server Error** | 服务器错误 | 重试 3 次后失败 | Toast 提示「服务器繁忙，请稍后重试」 |
| **Network Error** | 网络断开 | 检测网络恢复后重试 | 显示「网络已断开」横幅 |
| **Timeout** | 请求超时 | 取消请求，允许重试 | Toast 提示「请求超时，点击重试」 |

### 9.2 全局错误处理

```typescript
// api/client.ts
import axios, { AxiosError } from 'axios';
import { useAuthStore } from '@/stores/auth';
import { toast } from '@/components/ui/use-toast';

const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
});

// 请求拦截器：添加 Token
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：统一错误处理
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (!error.response) {
      // 网络错误
      toast({
        title: '网络错误',
        description: '请检查网络连接',
        variant: 'destructive',
      });
      return Promise.reject(error);
    }

    const { status } = error.response;

    switch (status) {
      case 401:
        useAuthStore.getState().logout();
        window.location.href = '/login';
        break;
      case 403:
        toast({
          title: '权限不足',
          description: '您没有权限执行此操作',
          variant: 'destructive',
        });
        break;
      case 500:
        toast({
          title: '服务器错误',
          description: '请稍后重试或联系管理员',
          variant: 'destructive',
        });
        break;
      default:
        toast({
          title: '请求失败',
          description: error.message || '未知错误',
          variant: 'destructive',
        });
    }

    return Promise.reject(error);
  }
);
```

### 9.3 React Error Boundary

```typescript
// components/ErrorBoundary.tsx
export class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode },
  { hasError: boolean; error?: Error }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
    // 可发送错误日志到监控服务
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div className="flex flex-col items-center justify-center min-h-screen p-4">
            <h1 className="text-2xl font-bold mb-4">出错了</h1>
            <p className="text-gray-600 mb-4">{this.state.error?.message}</p>
            <Button onClick={() => window.location.reload()}>刷新页面</Button>
          </div>
        )
      );
    }

    return this.props.children;
  }
}
```

---

## 10. 实时通信

### 10.1 WebSocket 消息格式

```typescript
// 客户端 -> 服务端
interface ClientMessage {
  type: 'subscribe' | 'ping';
  thread_id?: string;
}

// 服务端 -> 客户端
interface ServerMessage {
  type: 'status_update' | 'new_task' | 'task_resolved' | 'pong';
  payload: {
    thread_id?: string;
    status?: string;
    task?: Task;
    message?: string;
  };
}
```

### 10.2 连接管理

- 登录后建立 WebSocket 连接
- 心跳机制：30秒 ping/pong
- 断线自动重连（指数退避）
- 页面隐藏时降级为轮询

---

## 10. 路由设计

### 10.1 C 端路由

```typescript
// apps/customer/routes.tsx
const customerRoutes = [
  { path: '/login', element: <Login /> },
  { path: '/chat', element: <Chat />, auth: true },
  { path: '/', redirect: '/chat' },
];
```

### 10.2 B 端路由

```typescript
// apps/admin/routes.tsx
const adminRoutes = [
  { path: '/login', element: <Login /> },
  { path: '/dashboard', element: <Dashboard />, auth: true, admin: true },
  { path: '/', redirect: '/dashboard' },
];
```

---

## 11. 加载与空状态设计

### 11.1 加载状态

**骨架屏 (Skeleton)** - 用于初始加载：
```tsx
// 任务列表骨架屏
<TaskListSkeleton>
  ┌─────────────────┐
  │ ▓▓▓▓▓▓          │  <- 筛选器占位
  ├─────────────────┤
  │ ▓▓▓▓ ▓▓▓▓▓▓▓▓   │  <- 任务项占位 x5
  │ ▓▓▓▓ ▓▓▓▓       │
  ├─────────────────┤
  │ ▓▓▓▓ ▓▓▓▓▓▓▓▓   │
  │ ▓▓▓▓ ▓▓▓▓       │
  └─────────────────┘
</TaskListSkeleton>

// 聊天消息骨架屏
<ChatSkeleton>
  ┌─────────────────────────────────────┐
  │ ●▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓     │
  │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓                    │
  └─────────────────────────────────────┘
</ChatSkeleton>
```

**脉冲动画 (Pulse)** - 用于局部更新：
```tsx
// 发送中状态
<div className="animate-pulse bg-gray-200 rounded h-4 w-3/4" />
```

**加载按钮状态**：
```tsx
<Button disabled>
  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
  发送中...
</Button>
```

### 11.2 空状态

**任务列表空状态** (B 端)：
```
┌─────────────────────────────────┐
│                                 │
│           📋                    │
│      暂无待审核任务              │
│                                 │
│   当前没有需要人工审核的退款申请   │
│   新任务到达时会自动显示          │
│                                 │
│      [刷新列表]                 │
│                                 │
└─────────────────────────────────┘
```

**聊天记录空状态** (C 端)：
```
┌───────────────────────────────────────┐
│                                       │
│              🤖                       │
│        我是您的智能客服助手            │
│                                       │
│   我可以帮您：                         │
│   • 查询订单状态                       │
│   • 了解退货政策                       │
│   • 提交退货申请                       │
│                                       │
│   在下方输入框开始对话吧！              │
│                                       │
│   [快捷提问: 我的订单] [退货政策]       │
│                                       │
└───────────────────────────────────────┘
```

**搜索结果空状态**：
```
┌───────────────────────────────────────┐
│                                       │
│              🔍                       │
│         未找到相关订单                 │
│                                       │
│   请检查订单号是否正确                 │
│   或尝试查询「我的订单」查看全部订单    │
│                                       │
└───────────────────────────────────────┘
```

### 11.3 错误状态

**加载失败重试**：
```
┌───────────────────────────────────────┐
│                                       │
│              ⚠️                       │
│         加载失败                       │
│                                       │
│   网络连接异常，请检查网络后重试        │
│                                       │
│      [重新加载]                       │
│                                       │
└───────────────────────────────────────┘
```

---

## 12. 响应式策略

本项目**仅针对 Web 端**，采用固定最小宽度：

- **C端**: 最小宽度 768px（平板以上）
- **B端**: 最小宽度 1280px（桌面）

小于最小宽度时显示提示：「请使用桌面浏览器访问」

---

## 13. 性能优化

### 13.1 构建优化
- Vite 代码分割
- 路由懒加载
- 组件按需导入

### 13.2 运行时优化
- React.memo 缓存消息列表
- useMemo 缓存计算结果
- 虚拟滚动（消息列表超过 100 条）

### 13.3 网络优化
- TanStack Query 缓存
- 请求去重
- 乐观更新

---

## 14. 开发计划

### 第一阶段：基础搭建
1. 初始化 Vite + React + TypeScript 项目
2. 配置 Tailwind CSS + shadcn/ui
3. **配置 Vite 多页面构建**
4. 搭建目录结构
5. **配置 API 客户端（含 SSE 支持）**
6. **配置全局错误处理**
7. 实现认证状态管理

### 第二阶段：C 端实现
1. 登录页面（**含加载、错误状态**）
2. 聊天界面框架
3. 消息组件（**流式输出支持**）
4. 订单卡片组件
5. 快捷工具面板（**可折叠**）
6. **空状态/加载状态**
7. WebSocket 集成

### 第三阶段：B 端实现
1. 管理员登录
2. 三栏布局框架（**固定+自适应**）
3. 任务列表（**骨架屏加载**）
4. 任务详情
5. 决策面板
6. 实时通知（Toast）
7. **空状态/错误状态**

### 第四阶段：集成优化
1. 前后端联调
2. 生产构建配置
3. FastAPI 静态文件托管
4. **类型同步检查**
5. 性能优化
6. 测试验证

---

## 15. 验收标准

- [ ] C端用户可以正常登录、聊天
- [ ] 消息流式显示正常
- [ ] 订单卡片展示正确
- [ ] 审核状态提示正常
- [ ] B端管理员可以登录
- [ ] 任务列表实时更新
- [ ] 三栏布局正常显示
- [ ] 决策操作正常工作
- [ ] Toast 通知正常弹出
- [ ] WebSocket 连接稳定
- [ ] 生产构建可以正常部署

---

---

## 16. 类型同步方案

### 16.1 方案：手动维护（推荐）

由于项目规模适中，采用**手动维护 + 代码审查**确保前后端类型一致。

**后端参考** (`app/api/v1/schemas.py`):
```python
class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    is_admin: bool

class TaskResponse(BaseModel):
    audit_log_id: int
    thread_id: str
    user_id: int
    risk_level: Literal["HIGH", "MEDIUM", "LOW"]
    trigger_reason: str
    context_snapshot: dict
    created_at: datetime
```

**前端对应** (`frontend/src/types/index.ts`):
```typescript
export interface User {
  id: number;
  username: string;
  full_name: string;
  is_admin: boolean;
}

export interface Task {
  audit_log_id: number;
  thread_id: string;
  user_id: number;
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  trigger_reason: string;
  context_snapshot: ContextSnapshot;
  created_at: string; // ISO 8601 格式
}
```

### 16.2 类型检查清单

修改 API 响应结构时，按以下清单同步：

- [ ] 更新后端 Pydantic Schema
- [ ] 更新前端 TypeScript 类型
- [ ] 检查组件中类型使用
- [ ] 运行 TypeScript 编译检查
- [ ] 运行后端类型检查 (mypy)

---

## 17. 附录：开发环境配置

### 17.1 启动开发服务器

```bash
# 1. 启动后端
cd /home/zelon/projects/E-commerce-Smart-Agent
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# 2. 启动前端 (新终端)
cd frontend
npm install
npm run dev

# C端访问: http://localhost:5173
# B端访问: http://localhost:5173/admin.html
```

### 17.2 生产构建

```bash
cd frontend
npm run build

# 构建输出:
# dist/customer/  - C端文件
# dist/admin/     - B端文件
# dist/shared/    - 共享 chunk
```

---

**文档版本**: 1.1
**最后更新**: 2025-04-08
**更新说明**: 补充 Vite 配置、SSE 处理、错误处理、加载状态、类型同步方案
