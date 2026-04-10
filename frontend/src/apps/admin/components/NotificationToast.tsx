import { useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react'
import type { Notification } from '@/types'

interface NotificationToastProps {
  notifications: Notification[]
  onMarkAsRead: (id: string) => void
  onMarkAllAsRead: () => void
}

export function NotificationToast({
  notifications,
  onMarkAsRead,
  onMarkAllAsRead,
}: NotificationToastProps) {
  const unreadNotifications = notifications.filter((n) => !n.read)

  useEffect(() => {
    // Auto mark as read after 10 seconds
    const timers = unreadNotifications.map((n) =>
      setTimeout(() => {
        onMarkAsRead(n.id)
      }, 10000)
    )

    return () => {
      timers.forEach(clearTimeout)
    }
  }, [unreadNotifications, onMarkAsRead])

  if (unreadNotifications.length === 0) return null

  const getIcon = (type: string) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'warning':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />
      default:
        return <Info className="h-4 w-4 text-blue-500" />
    }
  }

  return (
    <div className="fixed bottom-4 right-4 space-y-2 z-50">
      {unreadNotifications.slice(0, 3).map((notification) => (
        <Card
          key={notification.id}
          className="p-4 w-80 shadow-lg animate-in slide-in-from-bottom-2"
        >
          <div className="flex items-start gap-3">
            {getIcon(notification.type)}
            <div className="flex-1">
              <h4 className="font-medium text-sm">{notification.title}</h4>
              <p className="text-sm text-gray-600">{notification.message}</p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => onMarkAsRead(notification.id)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </Card>
      ))}
      {unreadNotifications.length > 3 && (
        <Button variant="outline" size="sm" className="w-full" onClick={onMarkAllAsRead}>
          标记全部已读 ({unreadNotifications.length - 3} 更多)
        </Button>
      )}
    </div>
  )
}
