import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { LogOut, User } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useAuthStore } from '@/stores/auth';
import { useChat } from '@/hooks/useChat';
import { ChatMessage } from '../components/ChatMessage';
import { ChatInput } from '../components/ChatInput';
import { QuickActions } from '../components/QuickActions';

export function Chat() {
  const { user, logout } = useAuth();
  const userId = useAuthStore((state) => state.user?.user_id);
  const [showQuickActions, setShowQuickActions] = useState(true);
  const { messages, isStreaming, sendMessage } = useChat(undefined, userId);

  const handleSendMessage = async (content: string) => {
    setShowQuickActions(false);
    await sendMessage(content);
  };

  const handleQuickAction = (action: string) => {
    const actionMap: Record<string, string> = {
      order_status: '查询我的订单状态',
      return_policy: '退货政策是什么',
      shipping: '运费是多少',
      contact: '如何联系客服',
    };
    handleSendMessage(actionMap[action] || action);
  };

  return (
    <div className="flex flex-col h-screen bg-white">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b bg-white">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-brand-600">E-commerce Smart Agent</h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Avatar className="h-8 w-8">
              <AvatarFallback>
                <User className="h-4 w-4" />
              </AvatarFallback>
            </Avatar>
            <span>{user?.username}</span>
          </div>
          <Button variant="ghost" size="sm" onClick={logout}>
            <LogOut className="h-4 w-4 mr-1" />
            退出
          </Button>
        </div>
      </header>

      <Separator />

      {/* Chat Area */}
      <div className="flex-1 overflow-hidden">
        <ScrollArea className="h-full">
          <div className="max-w-3xl mx-auto px-4 py-6">
            {messages.length === 0 ? (
              <div className="text-center py-12">
                <h2 className="text-2xl font-bold text-gray-800 mb-2">有什么可以帮助您的？</h2>
                <p className="text-gray-500">询问订单、退货、运费等问题</p>
              </div>
            ) : (
              <div className="space-y-6">
                {messages.map((message) => (
                  <ChatMessage key={message.id} message={message} />
                ))}
                {isStreaming && (
                  <div className="flex items-center gap-2 text-gray-400 text-sm">
                    <div className="animate-pulse">AI 正在思考...</div>
                  </div>
                )}
              </div>
            )}
          </div>
        </ScrollArea>
      </div>

      {/* Input Area */}
      <div className="border-t bg-gray-50">
        <div className="max-w-3xl mx-auto px-4 py-4">
          {showQuickActions && messages.length === 0 && (
            <QuickActions onAction={handleQuickAction} />
          )}
          <ChatInput onSend={handleSendMessage} disabled={isStreaming} />
        </div>
      </div>
    </div>
  );
}
