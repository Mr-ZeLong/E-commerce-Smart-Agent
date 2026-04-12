import { useState } from 'react'
import { Plus, Loader2, FlaskConical, Play, Pause, Archive, BarChart3, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
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
import { useExperiments, useExperimentResults } from '@/hooks/useExperiments'
import type { Experiment, ExperimentVariant } from '@/types'

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('zh-CN')
}

function getStatusBadge(status: Experiment['status']) {
  const statusConfig = {
    draft: { label: '草稿', variant: 'secondary' as const },
    running: { label: '运行中', variant: 'default' as const },
    paused: { label: '已暂停', variant: 'outline' as const },
    completed: { label: '已完成', variant: 'destructive' as const },
  }
  const config = statusConfig[status]
  return <Badge variant={config.variant}>{config.label}</Badge>
}

interface VariantEditorProps {
  variants: ExperimentVariant[]
  onChange: (variants: ExperimentVariant[]) => void
}

function VariantEditor({ variants, onChange }: VariantEditorProps) {
  const addVariant = () => {
    onChange([...variants, { name: '', weight: 1 }])
  }

  const removeVariant = (index: number) => {
    onChange(variants.filter((_, i) => i !== index))
  }

  const updateVariant = (index: number, field: keyof ExperimentVariant, value: unknown) => {
    const updated = [...variants]
    updated[index] = { ...updated[index], [field]: value }
    onChange(updated)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Label>实验变体</Label>
        <Button type="button" variant="outline" size="sm" onClick={addVariant}>
          <Plus className="mr-1 h-4 w-4" />
          添加变体
        </Button>
      </div>
      
      {variants.length === 0 ? (
        <div className="text-sm text-muted-foreground">至少需要一个变体</div>
      ) : (
        <div className="space-y-3">
          {variants.map((variant, index) => (
            <div key={index} className="rounded-md border p-3 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">变体 {index + 1}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => removeVariant(index)}
                  className="text-red-600"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
              
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor={`variant-name-${index}`}>名称</Label>
                  <Input
                    id={`variant-name-${index}`}
                    value={variant.name}
                    onChange={(e) => updateVariant(index, 'name', e.target.value)}
                    placeholder="例如: control, variant_a"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`variant-weight-${index}`}>权重</Label>
                  <Input
                    id={`variant-weight-${index}`}
                    type="number"
                    min={1}
                    value={variant.weight}
                    onChange={(e) => updateVariant(index, 'weight', parseInt(e.target.value) || 1)}
                  />
                </div>
              </div>
              
              <div className="space-y-1">
                <Label htmlFor={`variant-prompt-${index}`}>系统提示词 (可选)</Label>
                <Textarea
                  id={`variant-prompt-${index}`}
                  value={variant.system_prompt || ''}
                  onChange={(e) => updateVariant(index, 'system_prompt', e.target.value || null)}
                  rows={2}
                  placeholder="留空则使用默认提示词"
                />
              </div>
              
              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-1">
                  <Label htmlFor={`variant-model-${index}`}>LLM 模型</Label>
                  <Input
                    id={`variant-model-${index}`}
                    value={variant.llm_model || ''}
                    onChange={(e) => updateVariant(index, 'llm_model', e.target.value || null)}
                    placeholder="例如: gpt-4"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`variant-topk-${index}`}>检索 Top-K</Label>
                  <Input
                    id={`variant-topk-${index}`}
                    type="number"
                    min={1}
                    value={variant.retriever_top_k || ''}
                    onChange={(e) => updateVariant(index, 'retriever_top_k', e.target.value ? parseInt(e.target.value) : null)}
                    placeholder="例如: 5"
                  />
                </div>
                <div className="flex items-end">
                  <Label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={variant.reranker_enabled || false}
                      onChange={(e) => updateVariant(index, 'reranker_enabled', e.target.checked || null)}
                      className="rounded border-gray-300"
                    />
                    启用重排序
                  </Label>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

interface ResultsDialogProps {
  experiment: Experiment | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

function ResultsDialog({ experiment, open, onOpenChange }: ResultsDialogProps) {
  const { data: results, isLoading } = useExperimentResults(experiment?.id)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>实验结果</DialogTitle>
          <DialogDescription>
            {experiment ? `实验 "${experiment.name}" 的变体分配统计` : ''}
          </DialogDescription>
        </DialogHeader>
        
        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-8">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载中...
          </div>
        ) : !results || results.length === 0 ? (
          <div className="text-sm text-muted-foreground py-8 text-center">
            暂无分配数据
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>变体名称</TableHead>
                <TableHead>权重</TableHead>
                <TableHead className="text-right">分配次数</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {results.map((result) => (
                <TableRow key={result.variant_id}>
                  <TableCell className="font-medium">{result.variant_name}</TableCell>
                  <TableCell>{result.weight}</TableCell>
                  <TableCell className="text-right">{result.assignments}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function ExperimentManager() {
  const {
    experiments,
    isLoading,
    createExperiment,
    isCreating,
    startExperiment,
    isStarting,
    pauseExperiment,
    isPausing,
    archiveExperiment,
    isArchiving,
  } = useExperiments()

  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [resultsDialogOpen, setResultsDialogOpen] = useState(false)
  const [selectedExperiment, setSelectedExperiment] = useState<Experiment | null>(null)
  
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [variants, setVariants] = useState<ExperimentVariant[]>([{ name: 'control', weight: 1 }])

  const handleCreate = async () => {
    if (!name.trim() || variants.length === 0) return
    
    await createExperiment({
      name: name.trim(),
      description: description.trim() || null,
      variants,
    })
    
    setCreateDialogOpen(false)
    setName('')
    setDescription('')
    setVariants([{ name: 'control', weight: 1 }])
  }

  const handleStart = async (experiment: Experiment) => {
    await startExperiment(experiment.id)
  }

  const handlePause = async (experiment: Experiment) => {
    await pauseExperiment(experiment.id)
  }

  const handleArchive = async (experiment: Experiment) => {
    await archiveExperiment(experiment.id)
  }

  const handleViewResults = (experiment: Experiment) => {
    setSelectedExperiment(experiment)
    setResultsDialogOpen(true)
  }

  const canStart = (status: Experiment['status']) => status === 'draft' || status === 'paused'
  const canPause = (status: Experiment['status']) => status === 'running'
  const canArchive = (status: Experiment['status']) => status === 'running' || status === 'paused'

  return (
    <div className="h-full overflow-auto bg-gray-100 p-4">
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex items-center gap-2">
          <FlaskConical className="h-5 w-5 text-muted-foreground" />
          <h1 className="text-xl font-semibold">A/B 实验管理</h1>
        </div>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <FlaskConical className="h-5 w-5 text-muted-foreground" />
              <CardTitle>实验列表</CardTitle>
            </div>
            <Button size="sm" onClick={() => setCreateDialogOpen(true)}>
              <Plus className="mr-1 h-4 w-4" />
              创建实验
            </Button>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                加载中...
              </div>
            ) : experiments.length === 0 ? (
              <div className="text-sm text-muted-foreground">暂无实验</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>实验名称</TableHead>
                    <TableHead>描述</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {experiments.map((experiment) => (
                    <TableRow key={experiment.id}>
                      <TableCell className="font-medium">{experiment.name}</TableCell>
                      <TableCell className="max-w-xs truncate text-muted-foreground">
                        {experiment.description || '-'}
                      </TableCell>
                      <TableCell>{getStatusBadge(experiment.status)}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(experiment.created_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          {canStart(experiment.status) && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => void handleStart(experiment)}
                              disabled={isStarting}
                            >
                              <Play className="h-4 w-4" />
                            </Button>
                          )}
                          {canPause(experiment.status) && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => void handlePause(experiment)}
                              disabled={isPausing}
                            >
                              <Pause className="h-4 w-4" />
                            </Button>
                          )}
                          {canArchive(experiment.status) && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => void handleArchive(experiment)}
                              disabled={isArchiving}
                            >
                              <Archive className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleViewResults(experiment)}
                          >
                            <BarChart3 className="h-4 w-4" />
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
      </div>

      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>创建实验</DialogTitle>
            <DialogDescription>
              创建新的 A/B 测试实验，定义实验变体和配置
            </DialogDescription>
          </DialogHeader>
          
          <div className="grid gap-6 py-4">
            <div className="grid gap-2">
              <Label htmlFor="experiment-name">实验名称</Label>
              <Input
                id="experiment-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="例如: 新提示词测试"
              />
            </div>
            
            <div className="grid gap-2">
              <Label htmlFor="experiment-description">实验描述</Label>
              <Textarea
                id="experiment-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                placeholder="描述实验目的和预期效果"
              />
            </div>
            
            <VariantEditor variants={variants} onChange={setVariants} />
          </div>
          
          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setCreateDialogOpen(false)}
              disabled={isCreating}
            >
              取消
            </Button>
            <Button
              type="button"
              onClick={() => void handleCreate()}
              disabled={isCreating || !name.trim() || variants.length === 0}
            >
              {isCreating ? '创建中...' : '创建'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ResultsDialog
        experiment={selectedExperiment}
        open={resultsDialogOpen}
        onOpenChange={setResultsDialogOpen}
      />
    </div>
  )
}