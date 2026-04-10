import { useState, useCallback } from 'react'
import type { Message } from '@/types'
import { API_BASE, getApiHeaders } from '@/lib/api'

const WELCOME_MESSAGE: Message = {
  id: 'welcome',
  role: 'assistant',
  content:
    '您好！我是您的电商智能助手。我可以帮您：\n• 查询订单状态\n• 解答退货政策\n• 处理退款申请\n\n请问有什么可以帮您的？',
  timestamp: new Date(),
}

interface StreamToken {
  token?: string
  type?: string
}

interface UseChatReturn {
  messages: Message[]
  isLoading: boolean
  sendMessage: (content: string, threadId: string) => Promise<void>
  resetMessages: () => void
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE])
  const [isLoading, setIsLoading] = useState(false)

  const sendMessage = useCallback(
    async (content: string, threadId: string) => {
      if (!content.trim() || isLoading) return

      const userMessage: Message = {
        id: `user_${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, userMessage])
      setIsLoading(true)

      const assistantMessageId = `assistant_${Date.now()}`
      setMessages((prev) => [
        ...prev,
        {
          id: assistantMessageId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          isStreaming: true,
        },
      ])

      try {
        const res = await fetch(`${API_BASE}/chat`, {
          method: 'POST',
          headers: getApiHeaders(),
          body: JSON.stringify({
            question: userMessage.content,
            thread_id: threadId,
          }),
        })

        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`)
        }

        const reader = res.body?.getReader()
        const decoder = new TextDecoder()
        let fullContent = ''

        if (reader) {
          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            const chunk = decoder.decode(value, { stream: true })
            const lines = chunk.split('\n')

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const data = line.slice(6)

                if (data === '[DONE]') {
                  setMessages((prev) =>
                    prev.map((msg) =>
                      msg.id === assistantMessageId ? { ...msg, isStreaming: false } : msg
                    )
                  )
                  continue
                }

                try {
                  const parsed = JSON.parse(data) as StreamToken
                  if (parsed.token) {
                    fullContent += parsed.token
                    setMessages((prev) =>
                      prev.map((msg) =>
                        msg.id === assistantMessageId ? { ...msg, content: fullContent } : msg
                      )
                    )
                  } else if (parsed.type === 'metadata') {
                    // 处理元数据（置信度等）
                  }
                } catch {
                  // 忽略解析错误
                }
              }
            }
          }
        }
      } catch {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  content: '抱歉，服务暂时不可用，请稍后重试。',
                  isStreaming: false,
                }
              : msg
          )
        )
      } finally {
        setIsLoading(false)
      }
    },
    [isLoading]
  )

  const resetMessages = useCallback(() => {
    setMessages([WELCOME_MESSAGE])
  }, [])

  return {
    messages,
    isLoading,
    sendMessage,
    resetMessages,
  }
}
