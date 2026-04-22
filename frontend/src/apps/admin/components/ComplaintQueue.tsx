import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useComplaints } from '@/hooks/useComplaints'
import type { ComplaintTicket, ComplaintFilters } from '@/types'
import { ShieldAlert, User, Clock, ChevronLeft, ChevronRight, Eye, UserPlus } from 'lucide-react'

function formatDate(iso: string | null | undefined) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

function UrgencyBadge({ urgency }: { urgency: ComplaintTicket['urgency'] }) {
  const variantMap: Record<ComplaintTicket['urgency'], 'destructive' | 'secondary' | 'outline'> = {
    high: 'destructive',
    medium: 'secondary',
    low: 'outline',
  }
  const labelMap: Record<ComplaintTicket['urgency'], string> = {
    high: '高',
    medium: '中',
    low: '低',
  }
  return (
    <Badge variant={variantMap[urgency]} className="capitalize">
      {labelMap[urgency]}
    </Badge>
  )
}

function StatusBadge({ status }: { status: ComplaintTicket['status'] }) {
  const variantMap: Record<
    ComplaintTicket['status'],
    'default' | 'secondary' | 'outline' | 'destructive'
  > = {
    open: 'default',
    in_progress: 'secondary',
    resolved: 'outline',
    closed: 'destructive',
  }
  const labelMap: Record<ComplaintTicket['status'], string> = {
    open: '待处理',
    in_progress: '处理中',
    resolved: '已解决',
    closed: '已关闭',
  }
  return (
    <Badge variant={variantMap[status]} className="capitalize">
      {labelMap[status]}
    </Badge>
  )
}

export function ComplaintQueue() {
  const [filters, setFilters] = useState<ComplaintFilters>({
    status: undefined,
    urgency: undefined,
    offset: 0,
    limit: 20,
  })
  const [selectedTicket, setSelectedTicket] = useState<ComplaintTicket | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [assignOpen, setAssignOpen] = useState(false)
  const [assignTarget, setAssignTarget] = useState<number | ''>('')
  const [resolveOpen, setResolveOpen] = useState(false)
  const [resolutionNotes, setResolutionNotes] = useState('')

  const {
    tickets,
    total,
    offset,
    limit,
    isLoading,
    error,
    assign,
    isAssigning,
    updateStatus,
    isUpdatingStatus,
    resolve,
    isResolving,
  } = useComplaints(filters)

  const handleFilterChange = (
    key: keyof ComplaintFilters,
    value: ComplaintFilters[keyof ComplaintFilters]
  ) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value,
      offset: 0,
    }))
  }

  const handlePrev = () => {
    setFilters((prev) => ({
      ...prev,
      offset: Math.max(0, (prev.offset || 0) - (prev.limit || 20)),
    }))
  }

  const handleNext = () => {
    if (offset + limit < total) {
      setFilters((prev) => ({
        ...prev,
        offset: (prev.offset || 0) + (prev.limit || 20),
      }))
    }
  }

  const handleViewDetail = (ticket: ComplaintTicket) => {
    setSelectedTicket(ticket)
    setDetailOpen(true)
  }

  const handleOpenAssign = (ticket: ComplaintTicket) => {
    setSelectedTicket(ticket)
    setAssignTarget(ticket.assigned_to ?? '')
    setAssignOpen(true)
  }

  const handleAssign = async () => {
    if (!selectedTicket || assignTarget === '') return
    await assign({ id: selectedTicket.id, assigned_to: Number(assignTarget) })
    setAssignOpen(false)
    setAssignTarget('')
  }

  const handleStatusUpdate = async (ticket: ComplaintTicket, status: ComplaintTicket['status']) => {
    await updateStatus({ id: ticket.id, status })
  }

  const handleOpenResolve = (ticket: ComplaintTicket) => {
    setSelectedTicket(ticket)
    setResolutionNotes('')
    setResolveOpen(true)
  }

  const handleResolve = async () => {
    if (!selectedTicket || !resolutionNotes.trim()) return
    await resolve({ id: selectedTicket.id, resolution_notes: resolutionNotes })
    setResolveOpen(false)
    setResolutionNotes('')
  }

  return (
    <div className="flex flex-col h-full gap-4 overflow-hidden">
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold">投诉管理</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">共 {total} 条投诉</span>
        </div>
      </div>

      <div className="flex items-center gap-4 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">状态:</span>
          <div className="flex gap-1">
            <Button
              variant={filters.status === undefined ? 'default' : 'outline'}
              size="sm"
              onClick={() => handleFilterChange('status', undefined)}
            >
              全部
            </Button>
            <Button
              variant={filters.status === 'open' ? 'default' : 'outline'}
              size="sm"
              onClick={() => handleFilterChange('status', 'open')}
            >
              待处理
            </Button>
            <Button
              variant={filters.status === 'in_progress' ? 'default' : 'outline'}
              size="sm"
              onClick={() => handleFilterChange('status', 'in_progress')}
            >
              处理中
            </Button>
            <Button
              variant={filters.status === 'resolved' ? 'default' : 'outline'}
              size="sm"
              onClick={() => handleFilterChange('status', 'resolved')}
            >
              已解决
            </Button>
            <Button
              variant={filters.status === 'closed' ? 'default' : 'outline'}
              size="sm"
              onClick={() => handleFilterChange('status', 'closed')}
            >
              已关闭
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">紧急度:</span>
          <div className="flex gap-1">
            <Button
              variant={filters.urgency === undefined ? 'default' : 'outline'}
              size="sm"
              onClick={() => handleFilterChange('urgency', undefined)}
            >
              全部
            </Button>
            <Button
              variant={filters.urgency === 'high' ? 'destructive' : 'outline'}
              size="sm"
              onClick={() => handleFilterChange('urgency', 'high')}
            >
              高
            </Button>
            <Button
              variant={filters.urgency === 'medium' ? 'secondary' : 'outline'}
              size="sm"
              onClick={() => handleFilterChange('urgency', 'medium')}
            >
              中
            </Button>
            <Button
              variant={filters.urgency === 'low' ? 'outline' : 'outline'}
              size="sm"
              onClick={() => handleFilterChange('urgency', 'low')}
            >
              低
            </Button>
          </div>
        </div>
      </div>

      {error && (
        <Alert variant="destructive" className="shrink-0">
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}

      <Card className="flex-1 min-h-0 overflow-hidden flex flex-col">
        <CardHeader className="shrink-0 pb-2">
          <CardTitle className="text-base">投诉队列</CardTitle>
          <CardDescription>
            显示 {tickets.length} / {total} 条记录
          </CardDescription>
        </CardHeader>
        <CardContent className="flex-1 min-h-0 overflow-auto p-0">
          {isLoading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">ID</TableHead>
                  <TableHead>类别</TableHead>
                  <TableHead className="w-20">紧急度</TableHead>
                  <TableHead className="w-20">状态</TableHead>
                  <TableHead>分配给</TableHead>
                  <TableHead className="w-40">创建时间</TableHead>
                  <TableHead className="text-right w-48">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tickets.map((ticket) => (
                  <TableRow key={ticket.id}>
                    <TableCell className="font-medium">{ticket.id}</TableCell>
                    <TableCell>{ticket.category}</TableCell>
                    <TableCell>
                      <UrgencyBadge urgency={ticket.urgency} />
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={ticket.status} />
                    </TableCell>
                    <TableCell>
                      {ticket.assigned_to ? (
                        <div className="flex items-center gap-1">
                          <User className="h-3 w-3" />
                          <span>管理员 #{ticket.assigned_to}</span>
                        </div>
                      ) : (
                        <span className="text-muted-foreground">未分配</span>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        <span className="text-xs">{formatDate(ticket.created_at)}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => handleViewDetail(ticket)}>
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenAssign(ticket)}
                          disabled={isAssigning}
                        >
                          <UserPlus className="h-4 w-4" />
                        </Button>
                        {ticket.status === 'open' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => void handleStatusUpdate(ticket, 'in_progress')}
                            disabled={isUpdatingStatus}
                          >
                            处理
                          </Button>
                        )}
                        {ticket.status === 'in_progress' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenResolve(ticket)}
                            disabled={isResolving}
                          >
                            解决
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {tickets.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                      暂无投诉记录
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
        <div className="flex items-center justify-between px-4 py-3 border-t shrink-0">
          <div className="text-sm text-muted-foreground">
            偏移 {offset} — {Math.min(offset + limit, total)} / {total}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePrev}
              disabled={offset === 0 || isLoading}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              上一页
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleNext}
              disabled={offset + limit >= total || isLoading}
            >
              下一页
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      </Card>

      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>投诉详情 #{selectedTicket?.id}</DialogTitle>
            <DialogDescription>查看投诉的详细信息</DialogDescription>
          </DialogHeader>
          {selectedTicket && (
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">类别</label>
                  <p className="text-sm">{selectedTicket.category}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">紧急度</label>
                  <div className="mt-1">
                    <UrgencyBadge urgency={selectedTicket.urgency} />
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">状态</label>
                  <div className="mt-1">
                    <StatusBadge status={selectedTicket.status} />
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">订单号</label>
                  <p className="text-sm">{selectedTicket.order_sn || '无'}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">用户ID</label>
                  <p className="text-sm">{selectedTicket.user_id}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">分配给</label>
                  <p className="text-sm">
                    {selectedTicket.assigned_to
                      ? `管理员 #${selectedTicket.assigned_to}`
                      : '未分配'}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">创建时间</label>
                  <p className="text-sm">{formatDate(selectedTicket.created_at)}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">更新时间</label>
                  <p className="text-sm">{formatDate(selectedTicket.updated_at)}</p>
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground">描述</label>
                <p className="text-sm mt-1 p-3 bg-muted rounded-md">{selectedTicket.description}</p>
              </div>
              {selectedTicket.expected_resolution && (
                <div>
                  <label className="text-sm font-medium text-muted-foreground">期望解决方案</label>
                  <p className="text-sm mt-1 p-3 bg-muted rounded-md">
                    {selectedTicket.expected_resolution}
                  </p>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetailOpen(false)}>
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={assignOpen} onOpenChange={setAssignOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>分配投诉 #{selectedTicket?.id}</DialogTitle>
            <DialogDescription>将投诉分配给管理员</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <label className="text-sm font-medium">管理员ID</label>
              <input
                type="number"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                value={assignTarget}
                onChange={(e) => setAssignTarget(e.target.value ? Number(e.target.value) : '')}
                placeholder="输入管理员ID"
              />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setAssignOpen(false)}
              disabled={isAssigning}
            >
              取消
            </Button>
            <Button
              type="button"
              onClick={() => void handleAssign()}
              disabled={isAssigning || assignTarget === ''}
            >
              {isAssigning ? '分配中...' : '确认分配'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={resolveOpen} onOpenChange={setResolveOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>解决投诉 #{selectedTicket?.id}</DialogTitle>
            <DialogDescription>输入解决方案并关闭投诉</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <label className="text-sm font-medium">解决方案</label>
              <textarea
                className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
                placeholder="请输入解决方案..."
              />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setResolveOpen(false)}
              disabled={isResolving}
            >
              取消
            </Button>
            <Button
              type="button"
              onClick={() => void handleResolve()}
              disabled={isResolving || !resolutionNotes.trim()}
            >
              {isResolving ? '解决中...' : '确认解决'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
