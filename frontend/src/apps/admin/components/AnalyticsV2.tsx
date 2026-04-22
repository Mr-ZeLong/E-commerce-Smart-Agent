import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  useCSATTrend,
  useComplaintRootCauses,
  useAgentComparison,
  useTraces,
} from '@/hooks/useAnalytics'
import { ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react'

function CSATTrendCard() {
  const { data: trends, isLoading, error } = useCSATTrend(30)

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle className="text-base">CSAT 趋势</CardTitle>
        <CardDescription>近 30 天每日平均 CSAT 分数</CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : error ? (
          <div className="text-sm text-destructive">{error.message}</div>
        ) : trends && trends.length > 0 ? (
          <div className="space-y-2">
            {trends.map((trend) => (
              <div key={trend.date} className="flex items-center justify-between text-sm">
                <span className="font-medium">{trend.date}</span>
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">{trend.count} 评价</span>
                  <Badge
                    variant={
                      trend.avg_score >= 4
                        ? 'default'
                        : trend.avg_score >= 3
                          ? 'secondary'
                          : 'destructive'
                    }
                  >
                      {trend.avg_score != null ? trend.avg_score.toFixed(2) : '-'}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">暂无数据</div>
        )}
      </CardContent>
    </Card>
  )
}

function RootCausesCard() {
  const { data: causes, isLoading, error } = useComplaintRootCauses()

  const maxCount = causes && causes.length > 0 ? Math.max(...causes.map((c) => c.count)) : 0

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle className="text-base">投诉根因</CardTitle>
        <CardDescription>按类别统计的投诉数量</CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : error ? (
          <div className="text-sm text-destructive">{error.message}</div>
        ) : causes && causes.length > 0 ? (
          <div className="space-y-3">
            {causes.map((cause) => {
              const pct = maxCount > 0 ? (cause.count / maxCount) * 100 : 0
              return (
                <div key={cause.category} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium truncate max-w-[60%]" title={cause.category}>
                      {cause.category}
                    </span>
                    <span className="text-muted-foreground">{cause.count}</span>
                  </div>
                  <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">暂无数据</div>
        )}
      </CardContent>
    </Card>
  )
}

function AgentComparisonCard() {
  const { data: agents, isLoading, error } = useAgentComparison(30)

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle className="text-base">Agent 对比</CardTitle>
        <CardDescription>各 Agent 的性能指标对比</CardDescription>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 overflow-hidden flex flex-col">
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : error ? (
          <div className="text-sm text-destructive">{error.message}</div>
        ) : agents && agents.length > 0 ? (
          <div className="flex-1 min-h-0 overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Agent</TableHead>
                  <TableHead className="text-right">会话数</TableHead>
                  <TableHead className="text-right">平均置信度</TableHead>
                  <TableHead className="text-right">转接率</TableHead>
                  <TableHead className="text-right">平均延迟</TableHead>
                  <TableHead className="text-right">投诉数</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {agents.map((agent) => (
                  <TableRow key={agent.final_agent}>
                    <TableCell className="font-medium">{agent.final_agent}</TableCell>
                    <TableCell className="text-right">{agent.total_sessions}</TableCell>
                    <TableCell className="text-right">
                      {agent.avg_confidence != null ? agent.avg_confidence.toFixed(4) : '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      {agent.transfer_rate != null
                        ? `${(agent.transfer_rate * 100).toFixed(2)}%`
                        : '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      {agent.avg_latency_ms != null ? `${agent.avg_latency_ms.toFixed(0)}ms` : '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      {agent.complaint_count != null ? agent.complaint_count : '-'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">暂无数据</div>
        )}
      </CardContent>
    </Card>
  )
}

function TracesCard() {
  const limit = 20
  const [offset, setOffset] = useState(0)
  const { data, isLoading, error } = useTraces(7, offset, limit)

  const traces = data?.traces ?? []
  const total = data?.total ?? 0

  const handlePrev = () => {
    setOffset((prev) => Math.max(0, prev - limit))
  }

  const handleNext = () => {
    if (offset + limit < total) {
      setOffset((prev) => prev + limit)
    }
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <Card className="flex flex-col">
      <CardHeader className="shrink-0 pb-2">
        <CardTitle className="text-base">追踪记录</CardTitle>
        <CardDescription>近 7 天的追踪记录，共 {total} 条</CardDescription>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 overflow-hidden flex flex-col">
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : error ? (
          <div className="text-sm text-destructive">{error.message}</div>
        ) : (
          <div className="flex-1 min-h-0 overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>时间</TableHead>
                  <TableHead>Thread ID</TableHead>
                  <TableHead>Agent</TableHead>
                  <TableHead className="text-right">置信度</TableHead>
                  <TableHead className="text-right">延迟</TableHead>
                  <TableHead>LangSmith</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {traces.map((trace) => (
                  <TableRow key={trace.id}>
                    <TableCell className="text-sm">{formatDate(trace.created_at)}</TableCell>
                    <TableCell
                      className="text-sm font-mono max-w-[120px] truncate"
                      title={trace.thread_id}
                    >
                      {trace.thread_id.slice(0, 8)}...
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{trace.final_agent || '-'}</Badge>
                    </TableCell>
                    <TableCell className="text-right text-sm">
                      {trace.confidence_score != null ? trace.confidence_score.toFixed(4) : '-'}
                    </TableCell>
                    <TableCell className="text-right text-sm">
                      {trace.total_latency_ms != null ? `${trace.total_latency_ms}ms` : '-'}
                    </TableCell>
                    <TableCell>
                      {trace.langsmith_run_url ? (
                        <a
                          href={trace.langsmith_run_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center text-sm text-blue-600 hover:text-blue-800"
                        >
                          查看
                          <ExternalLink className="h-3 w-3 ml-1" />
                        </a>
                      ) : (
                        <span className="text-sm text-muted-foreground">-</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
                {traces.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                      暂无追踪记录
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
      <div className="flex items-center justify-between px-4 py-3 border-t shrink-0">
        <div className="text-sm text-muted-foreground">
          {offset + 1} — {Math.min(offset + limit, total)} / {total}
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
  )
}

export function AnalyticsV2() {
  return (
    <div className="space-y-6 p-4 overflow-auto">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CSATTrendCard />
        <RootCausesCard />
      </div>
      <AgentComparisonCard />
      <TracesCard />
    </div>
  )
}
