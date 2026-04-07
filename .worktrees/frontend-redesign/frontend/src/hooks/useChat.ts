import { useState, useCallback } from 'react';
import { chatApi } from '@/api/chat';
import { useAuthStore } from '@/stores/auth';
import type { ChatMessage, ChatRequest } from '@/types';

export function useChat(conversationId?: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const token = useAuthStore((state) => state.token);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!token) {
        setError('Not authenticated');
        return;
      }

      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',
        content,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsStreaming(true);
      setError(null);

      const request: ChatRequest = {
        message: content,
        conversation_id: conversationId,
        user_id: useAuthStore.getState().user?.user_id || '',
      };

      try {
        const assistantMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: '',
          timestamp: new Date(),
        };

        setMessages((prev) => [...prev, assistantMessage]);

        for await (const event of chatApi.streamChat(request, token)) {
          if (event.type === 'delta' && event.content) {
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1];
              if (lastMessage?.role === 'assistant') {
                return [
                  ...prev.slice(0, -1),
                  { ...lastMessage, content: lastMessage.content + event.content },
                ];
              }
              return prev;
            });
          } else if (event.type === 'complete') {
            break;
          } else if (event.type === 'error') {
            setError(event.error || 'Stream error');
            break;
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsStreaming(false);
      }
    },
    [conversationId, token]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    isStreaming,
    error,
    sendMessage,
    clearMessages,
  };
}
