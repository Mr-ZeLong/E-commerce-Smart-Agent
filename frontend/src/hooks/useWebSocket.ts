import { useEffect, useRef, useState, useCallback } from 'react'
import type { WSMessage } from '@/types'

interface UseWebSocketOptions {
  url: string
  enabled?: boolean
  onMessage?: (message: WSMessage) => void
}

export function useWebSocket({ url, enabled = true, onMessage }: UseWebSocketOptions) {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const maxReconnectAttempts = 5

  const connect = useCallback(() => {
    if (!enabled || wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        reconnectAttemptsRef.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data) as WSMessage
          setLastMessage(parsed)
          onMessage?.(parsed)
        } catch (err) {
          console.error('[useWebSocket] Failed to parse message:', err)
        }
      }

      ws.onerror = (err) => {
        console.error('[useWebSocket] Connection error:', err)
      }

      ws.onclose = () => {
        setIsConnected(false)
        wsRef.current = null

        if (enabled && reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * 2 ** reconnectAttemptsRef.current, 30000)
          reconnectAttemptsRef.current += 1
          reconnectTimerRef.current = setTimeout(() => {
            connect()
          }, delay)
        }
      }
    } catch (err) {
      console.error('[useWebSocket] Failed to connect:', err)
    }
  }, [url, enabled, onMessage])

  useEffect(() => {
    if (enabled) {
      connect()
    }

    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect, enabled])

  const sendMessage = useCallback((message: WSMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  return {
    isConnected,
    lastMessage,
    sendMessage,
  }
}
