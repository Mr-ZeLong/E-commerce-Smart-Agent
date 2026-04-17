import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useConversations, useConversationMessages } from '@/hooks/useConversations'
import type { ConversationThread, ConversationMessage } from '@/types'
import { ChevronLeft, MessageCircle, User, Calendar } from 'lucide-react'

export function ConversationLogs() {
  const [selectedThread, setSelectedThread] = useState<ConversationThread | null>(null)
  const [userIdFilter, setUserIdFilter] = useState('')
  const [intentFilter, setIntentFilter] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const filters = {
    user_id: userIdFilter,
    intent_category: intentFilter,
    start_date: startDate,
    end_date: endDate,
  }

  const INTENT_OPTIONS = [
    { value: '', label: '全部意图' },
    { value: 'ORDER', label: 'ORDER' },
    { value: 'AFTER_SALES', label: 'AFTER_SALES' },
    { value: 'POLICY', label: 'POLICY' },
    { value: 'ACCOUNT', label: 'ACCOUNT' },
    { value: 'PROMOTION', label: 'PROMOTION' },
    { value: 'PAYMENT', label: 'PAYMENT' },
    { value: 'LOGISTICS', label: 'LOGISTICS' },
    { value: 'PRODUCT', label: 'PRODUCT' },
    { value: 'CART', label: 'CART' },
    { value: 'COMPLAINT', label: 'COMPLAINT' },
    { value: 'OTHER', label: 'OTHER' },
  ]

  const { conversations, total, isLoading: listLoading } = useConversations(filters)
  const { messages, isLoading: messagesLoading } = useConversationMessages(
    selectedThread?.thread_id ?? null
  )

  if (selectedThread) {
    return (
      <div className="flex flex-col h-full gap-4">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setSelectedThread(null)}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            返回列表
          </Button>
          <span className="text-sm text-gray-500">Thread: {selectedThread.thread_id}</span>
        </div>

        <Card className="flex-1 flex flex-col min-h-0">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">消息轨迹</CardTitle>
            <div className="flex gap-3 text-sm text-gray-500">
              <div className="flex items-center gap-1">
                <User className="h-4 w-4" />
                User ID: {selectedThread.user_id ?? '-'}
              </div>
              <div className="flex items-center gap-1">
                <MessageCircle className="h-4 w-4" />
                消息数: {selectedThread.message_count}
              </div>
            </div>
          </CardHeader>
          <CardContent className="flex-1 min-h-0 p-0">
            <ScrollArea className="h-full px-4 pb-4">
              {messagesLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : messages.length === 0 ? (
                <div className="text-center text-gray-500 py-8">暂无消息</div>
              ) : (
                <div className="space-y-4 pt-1">
                  {messages.map((msg) => (
                    <MessageBubble key={msg.id} message={msg} />
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full gap-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">筛选条件</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <div className="flex items-center gap-2">
              <span className="text-sm whitespace-nowrap">User ID</span>
              <Input
                placeholder="输入用户ID"
                value={userIdFilter}
                onChange={(e) => setUserIdFilter(e.target.value)}
                className="w-32 h-8 text-sm"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm whitespace-nowrap">意图</span>
              <select
                value={intentFilter}
                onChange={(e) => setIntentFilter(e.target.value)}
                className="h-8 text-sm border rounded px-2 bg-white"
              >
                {INTENT_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-gray-500" />
              <Input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-36 h-8 text-sm"
              />
              <span className="text-sm text-gray-500">至</span>
              <Input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-36 h-8 text-sm"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="flex-1 flex flex-col min-h-0">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            会话列表
            <Badge variant="secondary" className="ml-2">
              {total}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 min-h-0 p-0">
          <ScrollArea className="h-full px-4 pb-4">
            {listLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : conversations.length === 0 ? (
              <div className="text-center text-gray-500 py-8">暂无会话记录</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Thread ID</TableHead>
                    <TableHead>User ID</TableHead>
                    <TableHead>意图</TableHead>
                    <TableHead>消息数</TableHead>
                    <TableHead>最后更新</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {conversations.map((thread) => (
                    <TableRow key={thread.thread_id}>
                      <TableCell className="font-mono text-xs max-w-[180px] truncate">
                        {thread.thread_id}
                      </TableCell>
                      <TableCell>{thread.user_id ?? '-'}</TableCell>
                      <TableCell>
                        {thread.intent_category ? (
                          <Badge variant="outline" className="text-xs">
                            {thread.intent_category}
                          </Badge>
                        ) : (
                          '-'
                        )}
                      </TableCell>
                      <TableCell>{thread.message_count}</TableCell>
                      <TableCell className="text-sm text-gray-500 whitespace-nowrap">
                        {new Date(thread.last_updated).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" onClick={() => setSelectedThread(thread)}>
                          查看
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  )
}

function MessageBubble({ message }: { message: ConversationMessage }) {
  const isUser = message.sender_type === 'user'
  const isAgent = message.sender_type === 'agent'
  const contentText = extractText(message.content)

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
          isUser
            ? 'bg-blue-500 text-white'
            : isAgent
              ? 'bg-gray-100 text-gray-900'
              : 'bg-amber-50 text-amber-900 border'
        }`}
      >
        <div className="flex items-center gap-2 mb-1 opacity-80 text-xs">
          <Badge variant="outline" className="text-[10px] h-4 px-1">
            {message.sender_type}
          </Badge>
          <span>{new Date(message.created_at).toLocaleString()}</span>
        </div>
        <div className="whitespace-pre-wrap break-words">{contentText}</div>
        {message.message_type !== 'text' && (
          <div className="mt-1 text-xs opacity-70">type: {message.message_type}</div>
        )}
      </div>
    </div>
  )
}

function extractText(content: Record<string, unknown>): string {
  if (typeof content.text === 'string') {
    return content.text
  }
  if (typeof content.message === 'string') {
    return content.message
  }
  try {
    return JSON.stringify(content, null, 2)
  } catch {
    return '[Unable to display content]'
  }
}
