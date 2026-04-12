import { forwardRef } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { User, Bot, Loader2, ThumbsUp, ThumbsDown } from 'lucide-react'
import type { Message } from '@/types'

interface ChatMessageListProps {
  messages: Message[]
  isLoading: boolean
  onFeedback?: (messageId: string, sentiment: 'up' | 'down', messageIndex: number) => void
}

export const ChatMessageList = forwardRef<HTMLDivElement, ChatMessageListProps>(
  ({ messages, isLoading, onFeedback }, ref) => {
    let assistantMessageCount = 0
    
    return (
      <ScrollArea className="flex-1 p-4" ref={ref}>
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.map((msg) => {
            const isAssistant = msg.role === 'assistant'
            const currentMessageIndex = isAssistant ? assistantMessageCount++ : -1
            
            return (
              <div
                key={msg.id}
                className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                <Avatar className={msg.role === 'user' ? 'bg-blue-100' : 'bg-green-100'}>
                  <AvatarFallback>
                    {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                  </AvatarFallback>
                </Avatar>
                <div className="flex flex-col gap-2 max-w-[80%]">
                  <div
                    className={`rounded-lg px-4 py-2 whitespace-pre-wrap ${
                      msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-white border shadow-sm'
                    }`}
                  >
                    {msg.content}
                    {msg.isStreaming && (
                      <span className="inline-block w-2 h-4 ml-1 bg-gray-400 animate-pulse" />
                    )}
                  </div>
                  
                  {isAssistant && !msg.isStreaming && onFeedback && (
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className={`h-6 w-6 ${
                          msg.feedbackSentiment === 'up' 
                            ? 'text-blue-600 bg-blue-50 hover:bg-blue-100' 
                            : 'text-gray-400 hover:text-gray-600'
                        }`}
                        onClick={() => onFeedback(msg.id, 'up', currentMessageIndex)}
                        aria-label="Thumbs up"
                      >
                        <ThumbsUp className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className={`h-6 w-6 ${
                          msg.feedbackSentiment === 'down' 
                            ? 'text-red-600 bg-red-50 hover:bg-red-100' 
                            : 'text-gray-400 hover:text-gray-600'
                        }`}
                        onClick={() => onFeedback(msg.id, 'down', currentMessageIndex)}
                        aria-label="Thumbs down"
                      >
                        <ThumbsDown className="h-3 w-3" />
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
          {isLoading && messages[messages.length - 1]?.role === 'user' && (
            <div className="flex gap-3">
              <Avatar className="bg-green-100">
                <AvatarFallback>
                  <Bot className="w-4 h-4" />
                </AvatarFallback>
              </Avatar>
              <div className="rounded-lg px-4 py-2 bg-white border shadow-sm flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm text-gray-500">思考中...</span>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
    )
  }
)

ChatMessageList.displayName = 'ChatMessageList'
