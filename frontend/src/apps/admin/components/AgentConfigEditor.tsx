import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { AgentConfig, AgentConfigPayload } from '@/types'

interface AgentConfigEditorProps {
  agent: AgentConfig | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSave: (agentName: string, payload: AgentConfigPayload) => Promise<void>
  onRollback: (agentName: string) => Promise<void>
  isSaving: boolean
  isRollingBack: boolean
}

export function AgentConfigEditor({
  agent,
  open,
  onOpenChange,
  onSave,
  onRollback,
  isSaving,
  isRollingBack,
}: AgentConfigEditorProps) {
  const [systemPrompt, setSystemPrompt] = useState('')
  const [confidence, setConfidence] = useState(0.8)
  const [maxRetries, setMaxRetries] = useState(1)
  const [enabled, setEnabled] = useState(true)

  useEffect(() => {
    if (agent) {
      setSystemPrompt(agent.system_prompt)
      setConfidence(agent.confidence_threshold)
      setMaxRetries(agent.max_retries)
      setEnabled(agent.enabled)
    }
  }, [agent, open])

  const handleSave = async () => {
    if (!agent) return
    await onSave(agent.agent_name, {
      system_prompt: systemPrompt,
      confidence_threshold: confidence,
      max_retries: maxRetries,
      enabled,
    })
    onOpenChange(false)
  }

  const handleRollback = async () => {
    if (!agent) return
    await onRollback(agent.agent_name)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>编辑 Agent 配置</DialogTitle>
          <DialogDescription>
            {agent?.agent_name ? `正在编辑: ${agent.agent_name}` : ''}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 py-4">
          <div className="grid gap-2">
            <Label htmlFor="system-prompt">系统提示词 (System Prompt)</Label>
            <Textarea
              id="system-prompt"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={5}
              placeholder="输入系统提示词..."
            />
          </div>

          <div className="rounded-md border bg-muted/40 p-3">
            <p className="mb-1 text-xs font-medium text-muted-foreground">实时预览</p>
            <p className="whitespace-pre-wrap text-sm">{systemPrompt || '（无内容）'}</p>
          </div>

          <div className="grid gap-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="confidence">置信度阈值</Label>
              <span className="text-sm font-medium">{confidence.toFixed(2)}</span>
            </div>
            <input
              id="confidence"
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={confidence}
              onChange={(e) => setConfidence(parseFloat(e.target.value))}
              className="w-full accent-primary"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="max-retries">最大重试次数</Label>
            <Input
              id="max-retries"
              type="number"
              min={0}
              max={10}
              value={maxRetries}
              onChange={(e) => setMaxRetries(parseInt(e.target.value || '0', 10))}
            />
          </div>

          <div className="flex items-center justify-between rounded-md border p-3">
            <div className="space-y-0.5">
              <Label htmlFor="enabled">启用 Agent</Label>
              <p className="text-xs text-muted-foreground">关闭后该 Agent 将不再接收任何请求</p>
            </div>
            <Switch
              id="enabled"
              checked={enabled}
              onCheckedChange={setEnabled}
            />
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => void handleRollback()}
            disabled={!agent?.previous_system_prompt || isRollingBack || isSaving}
          >
            {isRollingBack ? '回滚中...' : '回滚提示词'}
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => onOpenChange(false)}
            disabled={isSaving || isRollingBack}
          >
            取消
          </Button>
          <Button
            type="button"
            onClick={() => void handleSave()}
            disabled={isSaving || isRollingBack}
          >
            {isSaving ? '保存中...' : '保存'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
