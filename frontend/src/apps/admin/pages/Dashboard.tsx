import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { LogOut, Bell, User, BarChart3, MessageSquare, BookOpen, Bot } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useTasks, useTaskStats } from '@/hooks/useTasks'
import { useNotifications } from '@/hooks/useNotifications'
import type { Task, TaskFilters } from '@/types'
import { TaskList } from '../components/TaskList'
import { TaskDetail } from '../components/TaskDetail'
import { DecisionPanel } from '../components/DecisionPanel'
import { NotificationToast } from '../components/NotificationToast'
import { Performance } from '../components/Performance'
import { EvaluationViewer } from '../components/EvaluationViewer'
import { ConversationLogs } from '../components/ConversationLogs'
import { KnowledgeBase } from '../pages/KnowledgeBase'
import { AgentConfig } from '../pages/AgentConfig'

export function Dashboard() {
  const { user, logout } = useAuth()
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [filters, setFilters] = useState<TaskFilters>({ riskLevel: 'ALL' })
  const { tasks, isLoading, submitDecision, isSubmitting } = useTasks(filters)
  const { data: stats } = useTaskStats()
  const { notifications, unreadCount, markAsRead, markAllAsRead } = useNotifications()

  const handleDecision = async (
    auditLogId: number,
    action: 'APPROVE' | 'REJECT',
    comment: string
  ) => {
    await submitDecision({
      audit_log_id: auditLogId,
      action,
      comment,
      admin_id: user?.user_id || '',
    })
    setSelectedTask(null)
  }

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      <header className="flex items-center justify-between px-6 py-4 bg-white border-b">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold">审核控制台</h1>
          {stats && (
            <div className="flex gap-2">
              <Badge variant="secondary">待审核: {stats.pending}</Badge>
              <Badge variant="destructive">高风险: {stats.high_risk}</Badge>
            </div>
          )}
        </div>

        <div className="flex items-center gap-4">
          <div className="relative">
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="h-5 w-5" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 h-5 w-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                  {unreadCount}
                </span>
              )}
            </Button>
          </div>

          <div className="flex items-center gap-2 text-sm">
            <User className="h-4 w-4" />
            <span>{user?.username}</span>
          </div>
          <Button variant="ghost" size="sm" onClick={logout}>
            <LogOut className="h-4 w-4 mr-1" />
            退出
          </Button>
        </div>
      </header>

      <Separator />

        <Tabs defaultValue="tasks" className="flex flex-col flex-1 overflow-hidden">
        <div className="px-6 py-2 bg-white border-b">
          <TabsList>
            <TabsTrigger value="tasks">任务队列</TabsTrigger>
            <TabsTrigger value="performance">性能指标</TabsTrigger>
            <TabsTrigger value="conversations" className="gap-1">
              <MessageSquare className="h-4 w-4" />
              会话日志
            </TabsTrigger>
            <TabsTrigger value="evaluation" className="gap-1">
              <BarChart3 className="h-4 w-4" />
              评测数据
            </TabsTrigger>
            <TabsTrigger value="knowledge" className="gap-1">
              <BookOpen className="h-4 w-4" />
              知识库
            </TabsTrigger>
            <TabsTrigger value="agent-config" className="gap-1">
              <Bot className="h-4 w-4" />
              Agent 配置
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="tasks" className="flex-1 overflow-hidden m-0">
          <div className="flex-1 grid grid-cols-[280px_1fr_320px] gap-4 p-4 overflow-hidden h-full">
            <TaskList
              tasks={tasks || []}
              isLoading={isLoading}
              filters={filters}
              onFilterChange={setFilters}
              selectedTask={selectedTask}
              onSelectTask={setSelectedTask}
            />

            <TaskDetail task={selectedTask} />

            <DecisionPanel
              task={selectedTask}
              onDecision={(auditLogId, action, comment) => {
                void handleDecision(auditLogId, action, comment)
              }}
              isSubmitting={isSubmitting}
            />
          </div>
        </TabsContent>

        <TabsContent value="conversations" className="flex-1 overflow-hidden m-0">
          <div className="h-full p-4">
            <ConversationLogs />
          </div>
        </TabsContent>

        <TabsContent value="performance" className="flex-1 overflow-hidden m-0">
          <Performance />
        </TabsContent>

        <TabsContent value="evaluation" className="flex-1 overflow-hidden m-0">
          <div className="h-full p-4">
            <EvaluationViewer />
          </div>
        </TabsContent>

        <TabsContent value="knowledge" className="flex-1 overflow-hidden m-0">
          <KnowledgeBase />
        </TabsContent>

        <TabsContent value="agent-config" className="flex-1 overflow-hidden m-0">
          <AgentConfig />
        </TabsContent>
      </Tabs>

      <NotificationToast
        notifications={notifications}
        onMarkAsRead={markAsRead}
        onMarkAllAsRead={markAllAsRead}
      />
    </div>
  )
}
