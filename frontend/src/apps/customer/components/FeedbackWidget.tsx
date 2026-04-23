import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { ThumbsUp, ThumbsDown, Send, X, AlertTriangle } from 'lucide-react'

export type FeedbackCategory = 'accuracy' | 'helpfulness' | 'tone' | 'speed' | 'other'

interface FeedbackWidgetProps {
  messageId: string
  messageIndex: number
  initialSentiment?: 'up' | 'down' | null
  confidenceScore?: number
  onSubmit: (
    messageId: string,
    sentiment: 'up' | 'down',
    messageIndex: number,
    category?: string,
    comment?: string
  ) => void
  onCancel?: () => void
  autoTrigger?: boolean
}

const CATEGORIES: { value: FeedbackCategory; label: string }[] = [
  { value: 'accuracy', label: '准确性' },
  { value: 'helpfulness', label: '有用性' },
  { value: 'tone', label: '语气态度' },
  { value: 'speed', label: '响应速度' },
  { value: 'other', label: '其他' },
]

export function FeedbackWidget({
  messageId,
  messageIndex,
  initialSentiment,
  confidenceScore,
  onSubmit,
  onCancel,
  autoTrigger = false,
}: FeedbackWidgetProps) {
  const [selectedSentiment, setSelectedSentiment] = useState<'up' | 'down' | null>(
    initialSentiment ?? null
  )
  const [selectedCategory, setSelectedCategory] = useState<FeedbackCategory | null>(null)
  const [comment, setComment] = useState('')
  const [isExpanded, setIsExpanded] = useState(autoTrigger)

  useEffect(() => {
    if (autoTrigger && confidenceScore !== undefined && confidenceScore < 0.6) {
      setIsExpanded(true)
    }
  }, [autoTrigger, confidenceScore])

  const handleSentimentClick = useCallback(
    (sentiment: 'up' | 'down') => {
      setSelectedSentiment(sentiment)
      setIsExpanded(true)
    },
    []
  )

  const handleSubmit = useCallback(() => {
    if (!selectedSentiment) return
    onSubmit(
      messageId,
      selectedSentiment,
      messageIndex,
      selectedCategory ?? undefined,
      comment.trim() || undefined
    )
    setIsExpanded(false)
  }, [messageId, messageIndex, selectedSentiment, selectedCategory, comment, onSubmit])

  const handleCancel = useCallback(() => {
    setSelectedSentiment(null)
    setSelectedCategory(null)
    setComment('')
    setIsExpanded(false)
    onCancel?.()
  }, [onCancel])

  const isLowConfidence = confidenceScore !== undefined && confidenceScore < 0.6

  return (
    <div className="flex flex-col gap-2">
      {isLowConfidence && (
        <div className="flex items-center gap-1.5 text-amber-600 text-xs">
          <AlertTriangle className="h-3 w-3" />
          <span>此回复置信度较低，请帮助我们改进</span>
        </div>
      )}

      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className={`h-7 w-7 ${
            selectedSentiment === 'up'
              ? 'text-blue-600 bg-blue-50 hover:bg-blue-100'
              : 'text-gray-400 hover:text-gray-600'
          }`}
          onClick={() => handleSentimentClick('up')}
          aria-label="点赞"
          aria-pressed={selectedSentiment === 'up'}
        >
          <ThumbsUp className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className={`h-7 w-7 ${
            selectedSentiment === 'down'
              ? 'text-red-600 bg-red-50 hover:bg-red-100'
              : 'text-gray-400 hover:text-gray-600'
          }`}
          onClick={() => handleSentimentClick('down')}
          aria-label="点踩"
          aria-pressed={selectedSentiment === 'down'}
        >
          <ThumbsDown className="h-3.5 w-3.5" />
        </Button>
      </div>

      {isExpanded && selectedSentiment && (
        <div className="flex flex-col gap-3 p-3 bg-gray-50 rounded-lg border animate-in fade-in slide-in-from-top-1 duration-200">
          <div className="space-y-2">
            <Label className="text-xs font-medium text-gray-700">反馈类别（可选）</Label>
            <div className="flex flex-wrap gap-2">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.value}
                  type="button"
                  onClick={() =>
                    setSelectedCategory(selectedCategory === cat.value ? null : cat.value)
                  }
                  className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                    selectedCategory === cat.value
                      ? 'bg-blue-100 border-blue-300 text-blue-700'
                      : 'bg-white border-gray-200 text-gray-600 hover:border-gray-300'
                  }`}
                  aria-pressed={selectedCategory === cat.value}
                >
                  {cat.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor={`feedback-comment-${messageId}`} className="text-xs font-medium text-gray-700">
              详细说明（可选）
            </Label>
            <Textarea
              id={`feedback-comment-${messageId}`}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="请描述您的问题或建议..."
              className="min-h-[60px] text-xs resize-none"
              maxLength={500}
            />
            <div className="text-xs text-gray-400 text-right">{comment.length}/500</div>
          </div>

          <div className="flex items-center justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancel}
              className="h-7 text-xs"
            >
              <X className="h-3 w-3 mr-1" />
              取消
            </Button>
            <Button
              size="sm"
              onClick={handleSubmit}
              className="h-7 text-xs"
              disabled={!selectedSentiment}
            >
              <Send className="h-3 w-3 mr-1" />
              提交反馈
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
