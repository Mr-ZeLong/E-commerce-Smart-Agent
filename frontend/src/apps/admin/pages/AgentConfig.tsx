import { useState } from 'react'
import {
  Edit,
  Loader2,
  Bot,
  Route,
  Settings,
  Plus,
  Trash2,
  History,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
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
import {
  useAgentConfig,
  useAgentReports,
  useAgentVersionMetrics,
  useAgentVersions,
} from '@/hooks/useAgentConfig'
import type { AgentConfig, RoutingRule, AgentConfigVersion } from '@/types'
import { AgentConfigEditor } from '../components/AgentConfigEditor'

function VersionMetrics({ agentName, versionId }: { agentName: string; versionId: number }) {
  const { data: metrics, isLoading } = useAgentVersionMetrics(agentName, versionId)
  if (isLoading) {
    return <div className="text-xs text-muted-foreground">加载指标中...</div>
  }
  if (!metrics) {
    return <div className="text-xs text-muted-foreground">暂无指标数据</div>
  }
  return (
    <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
      <div className="rounded border bg-muted/30 p-2">
        <div className="text-muted-foreground">总会话</div>
        <div className="font-medium">{metrics.total_sessions ?? '-'}</div>
      </div>
      <div className="rounded border bg-muted/30 p-2">
        <div className="text-muted-foreground">平均置信度</div>
        <div className="font-medium">
          {metrics.avg_confidence !== null ? metrics.avg_confidence.toFixed(4) : '-'}
        </div>
      </div>
      <div className="rounded border bg-muted/30 p-2">
        <div className="text-muted-foreground">接管率</div>
        <div className="font-medium">
          {metrics.transfer_rate != null ? `${(metrics.transfer_rate * 100).toFixed(2)}%` : '-'}
        </div>
      </div>
      <div className="rounded border bg-muted/30 p-2">
        <div className="text-muted-foreground">平均延迟(ms)</div>
        <div className="font-medium">
          {metrics.avg_latency_ms !== null ? metrics.avg_latency_ms.toFixed(2) : '-'}
        </div>
      </div>
    </div>
  )
}

function formatDate(iso: string | null | undefined) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

const EMPTY_RULE = {
  id: undefined as number | undefined,
  intent_category: '',
  target_agent: '',
  priority: 10,
  condition_json: undefined as Record<string, unknown> | undefined,
}

function computeDiff(current: AgentConfigVersion, previous: AgentConfigVersion | null): string[] {
  const diffs: string[] = []
  if (!previous) {
    diffs.push('首次版本快照')
    return diffs
  }
  if (current.system_prompt !== previous.system_prompt) {
    diffs.push('system_prompt 变更')
  }
  if (current.confidence_threshold !== previous.confidence_threshold) {
    diffs.push(
      `confidence_threshold: ${previous.confidence_threshold} → ${current.confidence_threshold}`
    )
  }
  if (current.max_retries !== previous.max_retries) {
    diffs.push(`max_retries: ${previous.max_retries} → ${current.max_retries}`)
  }
  if (current.enabled !== previous.enabled) {
    diffs.push(`enabled: ${previous.enabled} → ${current.enabled}`)
  }
  if (diffs.length === 0) {
    diffs.push('无显著变更')
  }
  return diffs
}

function PromptEffectReportList({ agentName }: { agentName: string }) {
  const { data: reports, isLoading } = useAgentReports(agentName)
  const { generateReport, isGeneratingReport } = useAgentConfig()

  const handleGenerate = () => {
    const now = new Date()
    const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1)
    const reportMonth = `${lastMonth.getFullYear()}-${String(lastMonth.getMonth() + 1).padStart(2, '0')}`
    void generateReport({ agentName, reportMonth })
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">月度效果报告</h3>
        <Button size="sm" variant="outline" onClick={handleGenerate} disabled={isGeneratingReport}>
          {isGeneratingReport ? (
            <>
              <Loader2 className="mr-1 h-4 w-4 animate-spin" />
              生成中...
            </>
          ) : (
            '生成上月报告'
          )}
        </Button>
      </div>
      {isLoading ? (
        <div className="text-xs text-muted-foreground">加载报告中...</div>
      ) : !reports || reports.length === 0 ? (
        <div className="text-xs text-muted-foreground">暂无月度报告</div>
      ) : (
        <div className="space-y-2">
          {reports.map((report) => (
            <div key={report.id} className="rounded border px-3 py-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium">{report.report_month}</span>
                <span className="text-xs text-muted-foreground">
                  会话数: {report.total_sessions}
                </span>
              </div>
              <div className="mt-1 grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                <div>
                  置信度: {report.avg_confidence !== null ? report.avg_confidence.toFixed(4) : '-'}
                </div>
                <div>
                  接管率: {report.transfer_rate != null ? `${(report.transfer_rate * 100).toFixed(2)}%` : '-'}
                </div>
                <div>
                  延迟: {report.avg_latency_ms !== null ? report.avg_latency_ms.toFixed(2) : '-'} ms
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
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
    rollbackToVersion,
    isRollingBackToVersion,
    saveRoutingRule,
    isSavingRule,
    deleteRoutingRule,
    isDeletingRule,
  } = useAgentConfig()

  const [selectedAgent, setSelectedAgent] = useState<AgentConfig | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)

  const [ruleDialogOpen, setRuleDialogOpen] = useState(false)
  const [ruleForm, setRuleForm] = useState(EMPTY_RULE)

  const [expandedVersionId, setExpandedVersionId] = useState<number | null>(null)

  const { data: versions, isLoading: isLoadingVersions } = useAgentVersions(
    selectedAgent?.agent_name
  )

  const handleToggle = async (agent: AgentConfig, enabled: boolean) => {
    await updateAgent({ agentName: agent.agent_name, payload: { enabled } })
  }

  const handleEdit = (agent: AgentConfig) => {
    setSelectedAgent(agent)
    setEditorOpen(true)
  }

  const handleSave = async (
    agentName: string,
    payload: {
      system_prompt?: string
      confidence_threshold?: number
      max_retries?: number
      enabled?: boolean
    }
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
                      <TableCell>
                        {agent.confidence_threshold != null
                          ? agent.confidence_threshold.toFixed(2)
                          : '-'}
                      </TableCell>
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
              <History className="h-5 w-5 text-muted-foreground" />
              <CardTitle>效果报告 — {selectedAgent.agent_name}</CardTitle>
            </CardHeader>
            <CardContent>
              <PromptEffectReportList agentName={selectedAgent.agent_name} />
            </CardContent>
          </Card>
        )}

        {selectedAgent && (
          <Card>
            <CardHeader className="flex flex-row items-center gap-2">
              <History className="h-5 w-5 text-muted-foreground" />
              <CardTitle>版本历史 — {selectedAgent.agent_name}</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoadingVersions ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  加载中...
                </div>
              ) : !versions || versions.length === 0 ? (
                <div className="text-sm text-muted-foreground">暂无版本记录</div>
              ) : (
                <div className="space-y-2">
                  {versions.map((version, index) => {
                    const previous = index < versions.length - 1 ? versions[index + 1] : null
                    const diffs = computeDiff(version, previous)
                    const isExpanded = expandedVersionId === version.id
                    return (
                      <div key={version.id} className="rounded-md border px-3 py-2 text-sm">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">版本 #{version.id}</span>
                            <Badge variant="outline" className="text-xs">
                              {diffs.join(' · ')}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground">
                              {formatDate(version.created_at)}
                            </span>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6"
                              onClick={() => setExpandedVersionId(isExpanded ? null : version.id)}
                            >
                              {isExpanded ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </Button>
                          </div>
                        </div>
                        {isExpanded && (
                          <div className="mt-2 space-y-2 border-t pt-2">
                            {selectedAgent && (
                              <VersionMetrics
                                agentName={selectedAgent.agent_name}
                                versionId={version.id}
                              />
                            )}
                            <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                              <div>置信度: {version.confidence_threshold}</div>
                              <div>重试: {version.max_retries}</div>
                              <div>状态: {version.enabled ? '启用' : '禁用'}</div>
                            </div>
                            <div className="rounded bg-muted/40 p-2 text-xs whitespace-pre-wrap">
                              {version.system_prompt || '（无系统提示词）'}
                            </div>
                            <div className="flex justify-end gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={isRollingBackToVersion}
                                onClick={() =>
                                  rollbackToVersion({
                                    agentName: selectedAgent.agent_name,
                                    versionId: version.id,
                                  })
                                }
                              >
                                回滚到此版本
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}
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
            <Button
              type="button"
              variant="secondary"
              onClick={() => setRuleDialogOpen(false)}
              disabled={isSavingRule}
            >
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
