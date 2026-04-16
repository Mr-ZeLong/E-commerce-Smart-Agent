import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card } from '@/components/ui/card'
import { LogOut, Bell, User, BarChart3, BarChart4, MessageSquare, BookOpen, Bot, FlaskConical, ShieldAlert, CheckCircle, AlertCircle, Info } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useTasks, useTaskStats } from '@/hooks/useTasks'
import { useNotifications } from '@/hooks/useNotifications'
import { useWebSocket } from '@/hooks/useWebSocket'
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
import { ExperimentManager } from '../components/ExperimentManager'
import { AnalyticsV2 } from '../components/AnalyticsV2'
import { ComplaintQueue } from '../components/ComplaintQueue'
import { FeedbackManager } from '../components/FeedbackManager'

export function Dashboard() {
  const { user, logout } = useAuth()
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [filters, setFilters] = useState<TaskFilters>({ riskLevel: 'ALL' })
  const { tasks, isLoading, submitDecision, isSubmitting } = useTasks(filters)
  const { data: stats } = useTaskStats()
  const { notifications, unreadCount, markAsRead, markAllAsRead, handleWsMessage } = useNotifications()
  const [showNotifications, setShowNotifications] = useState(false)
  const notificationRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (notificationRef.current && !notificationRef.current.contains(event.target as Node)) {
        setShowNotifications(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/admin/${user?.user_id ?? ''}`
  useWebSocket({ url: wsUrl, enabled: Boolean(user?.user_id), onMessage: handleWsMessage })

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

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="h-4 w-4 text-green-500 shrink-0" />
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
      case 'warning':
        return <AlertCircle className="h-4 w-4 text-yellow-500 shrink-0" />
      default:
        return <Info className="h-4 w-4 text-blue-500 shrink-0" />
    }
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
          <div className="relative" ref={notificationRef}>
            <Button
              variant="ghost"
              size="icon"
              className="relative"
              onClick={() => setShowNotifications((v) => !v)}
            >
              <Bell className="h-5 w-5" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 h-5 w-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                  {unreadCount}
                </span>
              )}
            </Button>
            {showNotifications && (
              <Card className="absolute right-0 top-full mt-2 w-80 z-50 shadow-lg">
                <div className="flex items-center justify-between px-4 py-3 border-b">
                  <span className="font-medium text-sm">通知</span>
                  {unreadCount > 0 && (
                    <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={markAllAsRead}>
                      全部已读
                    </Button>
                  )}
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="px-4 py-6 text-sm text-gray-500 text-center">暂无通知</div>
                  ) : (
                    notifications.slice(0, 20).map((n) => (
                      <div
                        key={n.id}
                        className={`px-4 py-3 border-b last:border-b-0 cursor-pointer hover:bg-gray-50 ${
                          !n.read ? 'bg-blue-50/40' : ''
                        }`}
                        onClick={() => markAsRead(n.id)}
                      >
                        <div className="flex items-start gap-2">
                          {getNotificationIcon(n.type)}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{n.title}</p>
                            <p className="text-xs text-gray-600 line-clamp-2">{n.message}</p>
                          </div>
                          {!n.read && <span className="h-2 w-2 bg-blue-500 rounded-full mt-1.5 shrink-0" />}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </Card>
            )}
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
            <TabsTrigger value="experiments" className="gap-1">
              <FlaskConical className="h-4 w-4" />
              实验
            </TabsTrigger>
            <TabsTrigger value="complaints" className="gap-1">
              <ShieldAlert className="h-4 w-4" />
              投诉
            </TabsTrigger>
            <TabsTrigger value="feedback" className="gap-1">
              <MessageSquare className="h-4 w-4" />
              反馈
            </TabsTrigger>
            <TabsTrigger value="analytics-v2" className="gap-1">
              <BarChart4 className="h-4 w-4" />
              分析V2
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

        <TabsContent value="experiments" className="flex-1 overflow-hidden m-0">
          <ExperimentManager />
        </TabsContent>

        <TabsContent value="complaints" className="flex-1 overflow-hidden m-0">
          <ComplaintQueue />
        </TabsContent>

        <TabsContent value="feedback" className="flex-1 overflow-hidden m-0">
          <FeedbackManager />
        </TabsContent>

        <TabsContent value="analytics-v2" className="flex-1 overflow-hidden m-0">
          <AnalyticsV2 />
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
