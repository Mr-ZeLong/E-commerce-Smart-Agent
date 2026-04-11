import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useSessionMetrics,
  useTransferMetrics,
  useConfidenceMetrics,
  useLatencyMetrics,
} from '@/hooks/useMetrics'

function StatCard({
  label,
  value,
  isLoading,
}: {
  label: string
  value: number
  isLoading: boolean
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-8 w-20" />
        ) : (
          <div className="text-3xl font-bold">{value.toLocaleString()}</div>
        )}
      </CardContent>
    </Card>
  )
}

function CardDescription({ children }: { children: React.ReactNode }) {
  return <div className="text-sm text-muted-foreground">{children}</div>
}

function SimpleBar({
  label,
  value,
  max,
  displayValue,
  colorClass,
}: {
  label: string
  value: number
  max: number
  displayValue: string
  colorClass: string
}) {
  const pct = max > 0 ? (value / max) * 100 : 0
  return (
    <div className="py-2">
      <div className="flex items-center justify-between text-sm mb-1">
        <span className="font-medium truncate max-w-[60%]" title={label}>
          {label}
        </span>
        <span className="text-muted-foreground">{displayValue}</span>
      </div>
      <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${colorClass}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export function Performance() {
  const { data: sessions, isLoading: sessionsLoading } = useSessionMetrics()
  const { data: transfers, isLoading: transfersLoading } = useTransferMetrics()
  const { data: confidence, isLoading: confidenceLoading } = useConfidenceMetrics()
  const { data: latency, isLoading: latencyLoading } = useLatencyMetrics()

  const transferMax =
    transfers && transfers.length > 0
      ? Math.max(...transfers.map((t) => t.transfer_rate))
      : 0

  const confidenceMax =
    confidence && confidence.length > 0
      ? Math.max(...confidence.map((c) => c.avg_confidence ?? 0))
      : 0

  const latencyValues = latency?.map((l) => l.p99_latency_ms ?? 0) ?? []
  const latencyMax = latencyValues.length > 0 ? Math.max(...latencyValues) : 0

  return (
    <div className="space-y-6 p-4 overflow-auto">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          label="近 24 小时会话"
          value={sessions?.['24h'] ?? 0}
          isLoading={sessionsLoading}
        />
        <StatCard
          label="近 7 天会话"
          value={sessions?.['7d'] ?? 0}
          isLoading={sessionsLoading}
        />
        <StatCard
          label="近 30 天会话"
          value={sessions?.['30d'] ?? 0}
          isLoading={sessionsLoading}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="text-base">人工转接率</CardTitle>
            <CardDescription>按 Agent 统计的转接比例</CardDescription>
          </CardHeader>
          <CardContent className="flex-1">
            {transfersLoading ? (
              <div className="space-y-4">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            ) : transfers && transfers.length > 0 ? (
              <div className="divide-y">
                {transfers.map((t) => (
                  <SimpleBar
                    key={t.final_agent}
                    label={t.final_agent}
                    value={t.transfer_rate}
                    max={transferMax}
                    displayValue={`${(t.transfer_rate * 100).toFixed(2)}% (${t.transfers}/${t.total})`}
                    colorClass="bg-blue-500"
                  />
                ))}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">暂无数据</div>
            )}
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="text-base">平均置信度</CardTitle>
            <CardDescription>按 Agent 统计的平均置信度得分</CardDescription>
          </CardHeader>
          <CardContent className="flex-1">
            {confidenceLoading ? (
              <div className="space-y-4">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            ) : confidence && confidence.length > 0 ? (
              <div className="divide-y">
                {confidence.map((c) => (
                  <SimpleBar
                    key={c.final_agent}
                    label={c.final_agent}
                    value={c.avg_confidence ?? 0}
                    max={confidenceMax}
                    displayValue={
                      c.avg_confidence !== null
                        ? c.avg_confidence.toFixed(4)
                        : '-'
                    }
                    colorClass="bg-emerald-500"
                  />
                ))}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">暂无数据</div>
            )}
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="text-base">P99 节点延迟</CardTitle>
            <CardDescription>按节点统计的 P99 延迟 (ms)</CardDescription>
          </CardHeader>
          <CardContent className="flex-1">
            {latencyLoading ? (
              <div className="space-y-4">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            ) : latency && latency.length > 0 ? (
              <div className="divide-y">
                {latency.map((l) => (
                  <SimpleBar
                    key={l.node_name}
                    label={l.node_name}
                    value={l.p99_latency_ms ?? 0}
                    max={latencyMax}
                    displayValue={
                      l.p99_latency_ms !== null
                        ? `${l.p99_latency_ms.toFixed(2)} ms`
                        : '-'
                    }
                    colorClass="bg-amber-500"
                  />
                ))}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">暂无数据</div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
