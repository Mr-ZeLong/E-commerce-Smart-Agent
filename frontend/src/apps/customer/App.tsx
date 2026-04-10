import { FC, useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Bot } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useChat } from './hooks/useChat'
import { ChatMessageList } from './components/ChatMessageList'
import { ChatInput } from './components/ChatInput'

const App: FC = () => {
  const { isAuthenticated, login, logout, isLoading: isLoginLoading, error: loginError } = useAuth()
  const { messages, isLoading, sendMessage } = useChat()
  const [input, setInput] = useState('')
  const [loginForm, setLoginForm] = useState({ username: '', password: '' })
  const scrollRef = useRef<HTMLDivElement>(null)
  const threadId = useRef(`thread_${Date.now()}`)

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

      {/* Chat Area */}
      <ChatMessageList messages={messages} isLoading={isLoading} ref={scrollRef} />

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
