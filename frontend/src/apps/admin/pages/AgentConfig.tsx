import { useState } from 'react'
import { Edit, Loader2, Bot, Route, Settings, Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useAgentConfig, useAgentAuditLog } from '@/hooks/useAgentConfig'
import type { AgentConfig, RoutingRule, AgentConfigAuditLog } from '@/types'
import { AgentConfigEditor } from '../components/AgentConfigEditor'

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('zh-CN')
}

const EMPTY_RULE = {
  id: undefined as number | undefined,
  intent_category: '',
  target_agent: '',
  priority: 10,
  condition_json: undefined as Record<string, unknown> | undefined,
}

function formatAuditChange(log: AgentConfigAuditLog) {
  return `${log.field_name}: ${log.old_value ?? '(空)'} → ${log.new_value ?? '(空)'}`
}

export function AgentConfig() {
  const {
    agents,
    routingRules,
    isLoading,
    updateAgent,
    isUpdating,
    rollbackAgent,
    isRollingBack,
    saveRoutingRule,
    isSavingRule,
    deleteRoutingRule,
    isDeletingRule,
  } = useAgentConfig()

  const [selectedAgent, setSelectedAgent] = useState<AgentConfig | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)

  const [ruleDialogOpen, setRuleDialogOpen] = useState(false)
  const [ruleForm, setRuleForm] = useState(EMPTY_RULE)

  const { data: auditLogs, isLoading: isLoadingAudit } = useAgentAuditLog(selectedAgent?.agent_name)

  const handleToggle = async (agent: AgentConfig, enabled: boolean) => {
    await updateAgent({ agentName: agent.agent_name, payload: { enabled } })
  }

  const handleEdit = (agent: AgentConfig) => {
    setSelectedAgent(agent)
    setEditorOpen(true)
  }

  const handleSave = async (
    agentName: string,
    payload: { system_prompt?: string; confidence_threshold?: number; max_retries?: number; enabled?: boolean }
  ) => {
    await updateAgent({ agentName, payload })
  }

  const handleRollback = async (agentName: string) => {
    await rollbackAgent(agentName)
  }

  const openCreateRule = () => {
    setRuleForm(EMPTY_RULE)
    setRuleDialogOpen(true)
  }

  const openEditRule = (rule: RoutingRule) => {
    setRuleForm({
      id: rule.id,
      intent_category: rule.intent_category,
      target_agent: rule.target_agent,
      priority: rule.priority,
      condition_json: rule.condition_json ?? undefined,
    })
    setRuleDialogOpen(true)
  }

  const handleSaveRule = async () => {
    await saveRoutingRule({
      id: ruleForm.id,
      intent_category: ruleForm.intent_category,
      target_agent: ruleForm.target_agent,
      priority: Number(ruleForm.priority),
      condition_json: ruleForm.condition_json,
    })
    setRuleDialogOpen(false)
    setRuleForm(EMPTY_RULE)
  }

  const handleDeleteRule = async (id: number) => {
    if (confirm('确定删除该路由规则吗？')) {
      await deleteRoutingRule(id)
    }
  }

  return (
    <div className="h-full overflow-auto bg-gray-100 p-4">
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex items-center gap-2">
          <Settings className="h-5 w-5 text-muted-foreground" />
          <h1 className="text-xl font-semibold">Agent 配置中心</h1>
        </div>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-muted-foreground" />
              <CardTitle>Agent 列表</CardTitle>
            </div>
            <Badge variant="secondary">共 {agents.length} 个</Badge>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                加载中...
              </div>
            ) : agents.length === 0 ? (
              <div className="text-sm text-muted-foreground">暂无 Agent 配置</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Agent 名称</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>置信度阈值</TableHead>
                    <TableHead>最大重试</TableHead>
                    <TableHead>更新时间</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {agents.map((agent) => (
                    <TableRow key={agent.agent_name}>
                      <TableCell className="font-medium">{agent.agent_name}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Switch
                            checked={agent.enabled}
                            onCheckedChange={(checked) => {
                              void handleToggle(agent, checked)
                            }}
                            disabled={isUpdating}
                          />
                          <span className="text-xs">
                            {agent.enabled ? (
                              <span className="text-green-600">启用</span>
                            ) : (
                              <span className="text-gray-500">禁用</span>
                            )}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>{agent.confidence_threshold.toFixed(2)}</TableCell>
                      <TableCell>{agent.max_retries}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(agent.updated_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" onClick={() => handleEdit(agent)}>
                          <Edit className="mr-1 h-4 w-4" />
                          编辑
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <Route className="h-5 w-5 text-muted-foreground" />
              <CardTitle>路由规则</CardTitle>
            </div>
            <Button size="sm" variant="outline" onClick={openCreateRule}>
              <Plus className="mr-1 h-4 w-4" />
              新增规则
            </Button>
          </CardHeader>
          <CardContent>
            {routingRules.length === 0 ? (
              <div className="text-sm text-muted-foreground">暂无路由规则</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>意图类别</TableHead>
                    <TableHead>目标 Agent</TableHead>
                    <TableHead>优先级</TableHead>
                    <TableHead>条件</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {routingRules.map((rule) => (
                    <TableRow key={rule.id}>
                      <TableCell className="font-medium">{rule.intent_category}</TableCell>
                      <TableCell>{rule.target_agent}</TableCell>
                      <TableCell>{rule.priority}</TableCell>
                      <TableCell className="max-w-xs truncate text-muted-foreground">
                        {rule.condition_json ? JSON.stringify(rule.condition_json) : '-'}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button variant="ghost" size="sm" onClick={() => openEditRule(rule)}>
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-600"
                            onClick={() => void handleDeleteRule(rule.id)}
                            disabled={isDeletingRule}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {selectedAgent && (
          <Card>
            <CardHeader className="flex flex-row items-center gap-2">
              <Settings className="h-5 w-5 text-muted-foreground" />
              <CardTitle>变更历史 — {selectedAgent.agent_name}</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoadingAudit ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  加载中...
                </div>
              ) : !auditLogs || auditLogs.length === 0 ? (
                <div className="text-sm text-muted-foreground">暂无变更记录</div>
              ) : (
                <div className="space-y-2">
                  {auditLogs.map((log) => (
                    <div key={log.id} className="rounded-md border px-3 py-2 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{formatAuditChange(log)}</span>
                        <span className="text-xs text-muted-foreground">{formatDate(log.created_at)}</span>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        操作人: 管理员 #{log.changed_by}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      <AgentConfigEditor
        agent={selectedAgent}
        open={editorOpen}
        onOpenChange={setEditorOpen}
        onSave={handleSave}
        onRollback={handleRollback}
        isSaving={isUpdating}
        isRollingBack={isRollingBack}
      />

      <Dialog open={ruleDialogOpen} onOpenChange={setRuleDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{ruleForm.id ? '编辑路由规则' : '新增路由规则'}</DialogTitle>
            <DialogDescription>
              {ruleForm.id ? `编辑规则 #${ruleForm.id}` : '创建新的意图到 Agent 的路由规则'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="intent_category">意图类别</Label>
              <Input
                id="intent_category"
                value={ruleForm.intent_category}
                onChange={(e) => setRuleForm({ ...ruleForm, intent_category: e.target.value })}
                placeholder="例如: ORDER"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="target_agent">目标 Agent</Label>
              <Input
                id="target_agent"
                value={ruleForm.target_agent}
                onChange={(e) => setRuleForm({ ...ruleForm, target_agent: e.target.value })}
                placeholder="例如: order_agent"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="priority">优先级</Label>
              <Input
                id="priority"
                type="number"
                value={ruleForm.priority}
                onChange={(e) => setRuleForm({ ...ruleForm, priority: Number(e.target.value) })}
                placeholder="0-100"
              />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button type="button" variant="secondary" onClick={() => setRuleDialogOpen(false)} disabled={isSavingRule}>
              取消
            </Button>
            <Button type="button" onClick={() => void handleSaveRule()} disabled={isSavingRule}>
              {isSavingRule ? '保存中...' : '保存'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
