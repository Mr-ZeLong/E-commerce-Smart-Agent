import { useEffect, useRef, useCallback } from 'react';
import { useWebSocketStore } from '@/stores/websocket';
import { useAuthStore } from '@/stores/auth';
import type { WebSocketMessage, Task, Notification } from '@/types';

const WS_URL = 'ws://localhost:8000/ws/notifications';

export function useNotifications() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const token = useAuthStore((state) => state.token);
  const { isConnected, isConnecting, notifications, unreadCount } =
    useWebSocketStore();
  const {
    setConnected,
    setConnecting,
    setError,
    addNotification,
    markAsRead,
    markAllAsRead,
    removeNotification,
  } = useWebSocketStore();

  const connect = useCallback(() => {
    if (!token || wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setConnecting(true);
    setError(null);

    try {
      wsRef.current = new WebSocket(`${WS_URL}?token=${token}`);

      wsRef.current.onopen = () => {
        setConnected(true);
        setConnecting(false);
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);

          if (message.type === 'notification' && message.payload) {
            addNotification(message.payload as Notification);
          } else if (message.type === 'task_update' && message.payload) {
            const task = message.payload as Task;
            addNotification({
              id: `task-${task.audit_log_id}`,
              type: 'info',
              title: '新任务待审核',
              message: `任务 #${task.audit_log_id} 需要审核`,
              task_id: task.audit_log_id,
              timestamp: new Date(),
              read: false,
            });
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      wsRef.current.onclose = () => {
        setConnected(false);
        setConnecting(false);

        // Auto reconnect after 5 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 5000);
      };

      wsRef.current.onerror = (_error) => {
        setError('WebSocket connection error');
        setConnected(false);
        setConnecting(false);
      };
    } catch (err) {
      setError('Failed to create WebSocket connection');
      setConnecting(false);
    }
  }, [token]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (token) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [token, connect, disconnect]);

  return {
    isConnected,
    isConnecting,
    notifications,
    unreadCount,
    connect,
    disconnect,
    markAsRead,
    markAllAsRead,
    removeNotification,
  };
}
