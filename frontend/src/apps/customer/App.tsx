import { FC, useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Bot, X } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useChat } from './hooks/useChat'
import { useWebSocket } from '@/hooks/useWebSocket'
import { ChatMessageList } from './components/ChatMessageList'
import { ChatInput } from './components/ChatInput'
import type { WSMessage } from '@/types'

interface StatusToast {
  id: string
  title: string
  message: string
}

const App: FC = () => {
  const { isAuthenticated, login, logout, isLoading: isLoginLoading, error: loginError } = useAuth()
  const { messages, isLoading, sendMessage, submitFeedback } = useChat()
  const [input, setInput] = useState('')
  const [loginForm, setLoginForm] = useState({ username: '', password: '' })
  const [toasts, setToasts] = useState<StatusToast[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)
  const threadId = useRef(`thread_${Date.now()}`)

  const addToast = (title: string, message: string) => {
    const id = `${Date.now()}_${Math.random()}`
    setToasts((prev) => [...prev, { id, title, message }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 5000)
  }

  const handleWsMessage = (msg: WSMessage) => {
    if (msg.type === 'status_change') {
      const payload = msg.payload as
        | { title?: string; message?: string; status?: string }
        | undefined
      const title = payload?.title || '状态更新'
      const message = payload?.message || payload?.status || '您的请求状态已更新'
      addToast(title, message)
    }
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/${threadId.current}`
  useWebSocket({ url: wsUrl, enabled: isAuthenticated, onMessage: handleWsMessage })

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await login(loginForm)
    } catch {
      // error is already handled by useAuth and displayed via loginError
    }
  }

  const handleSend = () => {
    if (!input.trim() || isLoading) return
    void sendMessage(input, threadId.current)
    setInput('')
  }

  const handleFeedback = (
    messageId: string,
    sentiment: 'up' | 'down',
    messageIndex: number,
    category?: string,
    comment?: string
  ) => {
    void submitFeedback(messageId, sentiment, threadId.current, messageIndex, category, comment)
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-center">用户登录</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => {
                void handleLogin(e)
              }}
              className="space-y-4"
            >
              <div>
                <label className="text-sm font-medium">用户名</label>
                <Input
                  value={loginForm.username}
                  onChange={(e) => setLoginForm({ ...loginForm, username: e.target.value })}
                  placeholder="请输入用户名"
                  required
                />
              </div>
              <div>
                <label className="text-sm font-medium">密码</label>
                <Input
                  type="password"
                  value={loginForm.password}
                  onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                  placeholder="请输入密码"
                  required
                />
              </div>
              {loginError && <p className="text-sm text-red-600">{loginError}</p>}
              <Button type="submit" className="w-full" disabled={isLoginLoading}>
                {isLoginLoading ? '登录中...' : '登录'}
              </Button>
              <p className="text-xs text-gray-500 text-center">
                提示：如果没有账号，请先在后端创建或使用注册接口
              </p>
            </form>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot className="w-6 h-6 text-blue-600" />
          <h1 className="text-lg font-semibold">智能客服助手</h1>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            logout()
          }}
        >
          退出登录
        </Button>
      </header>

      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="bg-white border shadow-lg rounded-lg px-4 py-3 min-w-[16rem] max-w-xs"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-gray-900">{toast.title}</p>
                <p className="text-xs text-gray-600 mt-0.5">{toast.message}</p>
              </div>
              <button
                type="button"
                className="text-gray-400 hover:text-gray-600"
                onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Chat Area */}
      <ChatMessageList
        messages={messages}
        isLoading={isLoading}
        ref={scrollRef}
        onFeedback={handleFeedback}
      />

      {/* Input Area */}
      <ChatInput
        value={input}
        onChange={setInput}
        onSend={handleSend}
        isLoading={isLoading}
        placeholder="输入消息..."
      />
    </div>
  )
}

export default App
