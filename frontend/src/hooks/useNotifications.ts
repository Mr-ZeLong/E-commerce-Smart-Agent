import { useState, useCallback } from 'react'
import type { Notification, WSMessage, WSNotification } from '@/types'

export function useNotifications(onWsMessage?: (message: WSMessage) => void) {
  const [notifications, setNotifications] = useState<Notification[]>([])

  const unreadCount = notifications.filter((n) => !n.read).length

  const markAsRead = (id: string) => {
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)))
  }

  const markAllAsRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
  }

  const handleWsMessage = useCallback(
    (message: WSMessage) => {
      if (message.type === 'notification') {
        const notif = message as WSNotification
        const newNotification: Notification = {
          id: `${Date.now()}_${Math.random()}`,
          title: notif.title,
          message: notif.message,
          type: notif.severity,
          read: false,
          created_at: notif.timestamp || new Date().toISOString(),
        }
        setNotifications((prev) => [newNotification, ...prev])
      }
      onWsMessage?.(message)
    },
    [onWsMessage]
  )

  return {
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
    handleWsMessage,
  }
}
