import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Send } from 'lucide-react'

interface ChatInputProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  isLoading: boolean
  placeholder?: string
}

export function ChatInput({ value, onChange, onSend, isLoading, placeholder }: ChatInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div className="bg-white border-t p-4">
      <div className="max-w-3xl mx-auto flex gap-2">
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || '输入消息...'}
          disabled={isLoading}
          className="flex-1"
        />
        <Button onClick={onSend} disabled={isLoading || !value.trim()}>
          <Send className="w-4 h-4" />
        </Button>
      </div>
      <p className="max-w-3xl mx-auto mt-2 text-xs text-gray-400 text-center">
        按 Enter 发送，Shift + Enter 换行
      </p>
    </div>
  )
}
