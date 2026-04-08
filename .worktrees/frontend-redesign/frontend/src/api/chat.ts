import type { ChatRequest, ChatStreamEvent } from '@/types';

export const chatApi = {
  // SSE streaming chat
  streamChat: async function* (
    request: ChatRequest,
    token: string
  ): AsyncGenerator<ChatStreamEvent> {
    const response = await fetch('/api/v1/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('Response body is null');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              return;
            }
            try {
              const event: ChatStreamEvent = JSON.parse(data);
              yield event;
            } catch (e) {
              console.error('Failed to parse SSE event:', e);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },

  // Get conversation history
  getHistory: async (conversationId: string, token: string) => {
    const response = await fetch(`/api/v1/chat/history/${conversationId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    return response.json();
  },
};
