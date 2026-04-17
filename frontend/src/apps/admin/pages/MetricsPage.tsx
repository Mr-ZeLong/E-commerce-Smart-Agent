import React, { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertTriangle, TrendingUp, TrendingDown, Activity, Clock, Shield, Zap, Calendar } from 'lucide-react'

import {
  useDashboardSummary,
  useIntentAccuracyTrend,
  useTransferReasons,
  useTokenUsage,
  useLatencyTrend,
  useDashboardAlerts,
  useRAGPrecision,
  useHallucinationRate,
} from '@/hooks/useMetricsDashboard'

type TimeRange = '24h' | '7d' | '30d'

const timeRangeConfig: Record<TimeRange, { hours: number; days: number; label: string }> = {
  '24h': { hours: 24, days: 1, label: '最近24小时' },
  '7d': { hours: 168, days: 7, label: '最近7天' },
  '30d': { hours: 720, days: 30, label: '最近30天' },
}

function SummaryCard({
  title,
  value,
  description,
  icon: Icon,
  trend,
}: {
  title: string
  value: string | number
  description: string
  icon: React.ElementType
  trend?: 'up' | 'down' | 'neutral'
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <div className="flex items-center text-xs text-muted-foreground">
          {trend === 'up' && <TrendingUp className="mr-1 h-3 w-3 text-green-500" />}
          {trend === 'down' && <TrendingDown className="mr-1 h-3 w-3 text-red-500" />}
          {description}
        </div>
      </CardContent>
    </Card>
  )
}

function AlertsPanel({ alerts, isLoading, error }: {
  alerts: ReturnType<typeof useDashboardAlerts>['data']
  isLoading: boolean
  error: ReturnType<typeof useDashboardAlerts>['error']
}) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">实时告警</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">实时告警</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-destructive">加载失败</div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">实时告警</CardTitle>
        <CardDescription>
          {alerts && alerts.length > 0 ? `${alerts.length} 个活跃告警` : '系统正常'}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {alerts && alerts.length > 0 ? (
          <div className="space-y-3">
            {alerts.map((alert, index) => (
              <div
                key={index}
                className={`flex items-start gap-3 rounded-lg border p-3 ${
                  alert.severity === 'high'
                    ? 'border-red-200 bg-red-50'
                    : alert.severity === 'medium'
                      ? 'border-yellow-200 bg-yellow-50'
                      : 'border-blue-200 bg-blue-50'
                }`}
              >
                <AlertTriangle
                  className={`h-4 w-4 mt-0.5 ${
                    alert.severity === 'high'
                      ? 'text-red-500'
                      : alert.severity === 'medium'
                        ? 'text-yellow-500'
                        : 'text-blue-500'
                  }`}
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{alert.metric}</span>
                    <Badge
                      variant={alert.severity === 'high' ? 'destructive' : 'secondary'}
                      className="text-xs"
                    >
                      {alert.severity}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{alert.message}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
            <Shield className="h-4 w-4 mr-2 text-green-500" />
            暂无告警
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function IntentAccuracyCard({ trends, isLoading, error }: {
  trends: ReturnType<typeof useIntentAccuracyTrend>['data']
  isLoading: boolean
  error: ReturnType<typeof useIntentAccuracyTrend>['error']
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">意图识别准确率趋势</CardTitle>
        <CardDescription>按意图分类的准确率</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : error ? (
          <div className="text-sm text-destructive">加载失败</div>
        ) : trends && trends.length > 0 ? (
          <div className="space-y-2">
            {trends.slice(0, 10).map((trend, index) => (
              <div key={index} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{trend.intent_category}</span>
                  <span className="text-muted-foreground">{trend.total} 次</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-2 w-24 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-green-500"
                      style={{ width: `${trend.accuracy * 100}%` }}
                    />
                  </div>
                  <span className="text-xs w-12 text-right">
                    {(trend.accuracy * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground text-center py-8">暂无数据</div>
        )}
      </CardContent>
    </Card>
  )
}

function TransferReasonsCard({ reasons, isLoading, error }: {
  reasons: ReturnType<typeof useTransferReasons>['data']
  isLoading: boolean
  error: ReturnType<typeof useTransferReasons>['error']
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">人工转接原因</CardTitle>
        <CardDescription>按原因分类的转接统计</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : error ? (
          <div className="text-sm text-destructive">加载失败</div>
        ) : reasons && reasons.length > 0 ? (
          <div className="space-y-3">
            {reasons.map((reason, index) => (
              <div key={index} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{reason.reason}</span>
                  <span className="text-muted-foreground">
                    {reason.count} ({reason.percentage}%)
                  </span>
                </div>
                <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-orange-500"
                    style={{ width: `${reason.percentage}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground text-center py-8">暂无数据</div>
        )}
      </CardContent>
    </Card>
  )
}

function TokenUsageCard({ usage, isLoading, error }: {
  usage: ReturnType<typeof useTokenUsage>['data']
  isLoading: boolean
  error: ReturnType<typeof useTokenUsage>['error']
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Token 使用量</CardTitle>
        <CardDescription>Token消耗趋势</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : error ? (
          <div className="text-sm text-destructive">加载失败</div>
        ) : usage && usage.length > 0 ? (
          <div className="space-y-2">
            {usage.map((item, index) => (
              <div key={index} className="flex items-center justify-between text-sm">
                <span className="font-medium">{item.date.slice(0, 10)}</span>
                <div className="flex items-center gap-4">
                  <span className="text-muted-foreground">
                    {item.input_tokens.toLocaleString()} input
                  </span>
                  <span className="text-muted-foreground">
                    {item.total_tokens.toLocaleString()} total
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground text-center py-8">暂无数据</div>
        )}
      </CardContent>
    </Card>
  )
}

function LatencyTrendCard({ trends, isLoading, error }: {
  trends: ReturnType<typeof useLatencyTrend>['data']
  isLoading: boolean
  error: ReturnType<typeof useLatencyTrend>['error']
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">延迟趋势</CardTitle>
        <CardDescription>延迟统计 (ms)</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : error ? (
          <div className="text-sm text-destructive">加载失败</div>
        ) : trends && trends.length > 0 ? (
          <div className="space-y-2">
            {trends.slice(0, 12).map((trend, index) => (
              <div key={index} className="flex items-center justify-between text-sm">
                <span className="font-medium">{trend.hour.slice(11, 16)}</span>
                <div className="flex items-center gap-4">
                  <span className="text-muted-foreground">avg: {trend.avg_latency_ms}ms</span>
                  <span className="text-muted-foreground">p95: {trend.p95_latency_ms}ms</span>
                  <span className="text-muted-foreground">p99: {trend.p99_latency_ms}ms</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground text-center py-8">暂无数据</div>
        )}
      </CardContent>
    </Card>
  )
}

function RAGPrecisionCard({ items, isLoading, error }: {
  items: ReturnType<typeof useRAGPrecision>['data']
  isLoading: boolean
  error: ReturnType<typeof useRAGPrecision>['error']
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">RAG 检索精度</CardTitle>
        <CardDescription>RAG检索得分分布</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : error ? (
          <div className="text-sm text-destructive">加载失败</div>
        ) : items && items.length > 0 ? (
          <div className="space-y-2">
            {items.map((item, index) => (
              <div key={index} className="flex items-center justify-between text-sm">
                <span className="font-medium">{item.date.slice(0, 10)}</span>
                <div className="flex items-center gap-4">
                  <span className="text-muted-foreground">avg: {item.avg_score.toFixed(2)}</span>
                  <span className="text-muted-foreground">{item.count} queries</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground text-center py-8">暂无数据</div>
        )}
      </CardContent>
    </Card>
  )
}

function HallucinationRateCard({ items, isLoading, error }: {
  items: ReturnType<typeof useHallucinationRate>['data']
  isLoading: boolean
  error: ReturnType<typeof useHallucinationRate>['error']
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">幻觉率</CardTitle>
        <CardDescription>定时抽检幻觉率</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : error ? (
          <div className="text-sm text-destructive">加载失败</div>
        ) : items && items.length > 0 ? (
          <div className="space-y-2">
            {items.map((item, index) => (
              <div key={index} className="flex items-center justify-between text-sm">
                <span className="font-medium">{item.date.slice(0, 10)}</span>
                <div className="flex items-center gap-4">
                  <span className="text-muted-foreground">
                    {(item.hallucination_rate * 100).toFixed(1)}%
                  </span>
                  <span className="text-muted-foreground">{item.sampled_count} sampled</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground text-center py-8">暂无数据</div>
        )}
      </CardContent>
    </Card>
  )
}

export function MetricsPage() {
  const [timeRange, setTimeRange] = useState<TimeRange>('24h')
  const config = timeRangeConfig[timeRange]

  const { data: summary, isLoading: summaryLoading } = useDashboardSummary(config.hours)
  const { data: intentAccuracy, isLoading: intentLoading, error: intentError } = useIntentAccuracyTrend(config.hours)
  const { data: transferReasons, isLoading: transferLoading, error: transferError } = useTransferReasons(config.days)
  const { data: tokenUsage, isLoading: tokenLoading, error: tokenError } = useTokenUsage(config.days)
  const { data: latencyTrend, isLoading: latencyLoading, error: latencyError } = useLatencyTrend(config.hours)
  const { data: ragPrecision, isLoading: ragLoading, error: ragError } = useRAGPrecision(config.days)
  const { data: hallucinationRate, isLoading: hallLoading, error: hallError } = useHallucinationRate(config.days)
  const { data: alerts, isLoading: alertsLoading, error: alertsError } = useDashboardAlerts(config.hours)

  return (
    <div className="space-y-6 p-4 overflow-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">生产监控看板</h1>
          <p className="text-muted-foreground">实时监控系统核心指标和性能趋势</p>
        </div>
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as TimeRange)}
            className="h-9 w-[160px] rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <option value="24h">最近24小时</option>
            <option value="7d">最近7天</option>
            <option value="30d">最近30天</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {summaryLoading ? (
          <>
            {Array.from({ length: 6 }).map((_, i) => (
              <Card key={i}>
                <CardHeader className="pb-2">
                  <Skeleton className="h-4 w-24" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-8 w-16 mb-2" />
                  <Skeleton className="h-3 w-32" />
                </CardContent>
              </Card>
            ))}
          </>
        ) : summary ? (
          <>
            <SummaryCard
              title="24h 会话数"
              value={summary.total_sessions_24h.toLocaleString()}
              description={`7天: ${summary.total_sessions_7d.toLocaleString()}`}
              icon={Activity}
            />
            <SummaryCard
              title="平均置信度"
              value={
                summary.avg_confidence_24h
                  ? `${(summary.avg_confidence_24h * 100).toFixed(1)}%`
                  : '-'
              }
              description="近24小时"
              icon={TrendingUp}
              trend={summary.avg_confidence_24h && summary.avg_confidence_24h > 0.7 ? 'up' : 'down'}
            />
            <SummaryCard
              title="转接率"
              value={`${(summary.transfer_rate_24h * 100).toFixed(1)}%`}
              description="近24小时"
              icon={TrendingDown}
              trend={summary.transfer_rate_24h > 0.3 ? 'down' : 'up'}
            />
            <SummaryCard
              title="平均延迟"
              value={
                summary.avg_latency_ms_24h ? `${summary.avg_latency_ms_24h.toFixed(0)}ms` : '-'
              }
              description="近24小时"
              icon={Clock}
            />
            <SummaryCard
              title="Containment"
              value={`${(summary.containment_rate_24h * 100).toFixed(1)}%`}
              description="未转接比例"
              icon={Shield}
            />
            <SummaryCard
              title="Token 效率"
              value={
                summary.token_efficiency_24h
                  ? `${(summary.token_efficiency_24h * 100).toFixed(1)}%`
                  : '-'
              }
              description="Context utilization"
              icon={Zap}
            />
          </>
        ) : null}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <AlertsPanel alerts={alerts} isLoading={alertsLoading} error={alertsError} />
        <IntentAccuracyCard trends={intentAccuracy} isLoading={intentLoading} error={intentError} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TransferReasonsCard reasons={transferReasons} isLoading={transferLoading} error={transferError} />
        <TokenUsageCard usage={tokenUsage} isLoading={tokenLoading} error={tokenError} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <RAGPrecisionCard items={ragPrecision} isLoading={ragLoading} error={ragError} />
        <HallucinationRateCard items={hallucinationRate} isLoading={hallLoading} error={hallError} />
      </div>

      <LatencyTrendCard trends={latencyTrend} isLoading={latencyLoading} error={latencyError} />
    </div>
  )
}
