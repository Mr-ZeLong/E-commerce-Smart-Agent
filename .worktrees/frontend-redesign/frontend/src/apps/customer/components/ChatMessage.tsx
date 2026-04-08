import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { User, Bot } from 'lucide-react';
import type { ChatMessage as ChatMessageType } from '@/types';

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className="flex gap-4">
      <Avatar className={`h-8 w-8 ${isUser ? 'bg-gray-200' : 'bg-brand-100'}`}>
        <AvatarFallback>
          {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4 text-brand-600" />}
        </AvatarFallback>
      </Avatar>
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium">{isUser ? '您' : 'AI 助手'}</span>
          <span className="text-xs text-gray-400">
            {message.timestamp.toLocaleTimeString()}
          </span>
        </div>
        <div className="text-gray-800 whitespace-pre-wrap">
          {message.content}
        </div>
        {message.metadata?.order_data && (
          <div className="mt-2 p-3 bg-gray-50 rounded border border-l-4 border-l-brand-500">
            <div className="font-medium">订单: {message.metadata.order_data.order_sn}</div>
            <div className="text-sm text-gray-600">
              金额: ¥{message.metadata.order_data.total_amount}
            </div>
            <div className="text-sm text-gray-600">
              状态: {message.metadata.order_data.status}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
