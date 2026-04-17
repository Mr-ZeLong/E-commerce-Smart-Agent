import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useEvaluationDataset, useRunEvaluation } from '@/hooks/useEvaluation'
import { ChevronLeft, ChevronRight, Play, RefreshCw } from 'lucide-react'

export function EvaluationViewer() {
  const [limit, setLimit] = useState(10)
  const [offset, setOffset] = useState(0)
  const { data, isLoading, error } = useEvaluationDataset(limit, offset)
  const { mutateAsync: runEvaluation, isPending: isRunning, data: results } = useRunEvaluation()

  const records = data?.records ?? []
  const total = data?.total ?? 0

  const handlePrev = () => {
    setOffset((prev) => Math.max(0, prev - limit))
  }

  const handleNext = () => {
    if (offset + limit < total) {
      setOffset((prev) => prev + limit)
    }
  }

  const formatMetric = (value: number | undefined) => {
    if (value === undefined) return '-'
    return `${(value * 100).toFixed(1)}%`
  }

  return (
    <div className="flex flex-col h-full gap-4 overflow-hidden">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 shrink-0">
        <MetricCard
          label="Intent Accuracy"
          value={formatMetric(results?.intent_accuracy)}
          isLoading={isRunning}
        />
        <MetricCard
          label="Slot Recall"
          value={formatMetric(results?.slot_recall)}
          isLoading={isRunning}
        />
        <MetricCard
          label="RAG Precision"
          value={formatMetric(results?.rag_precision)}
          isLoading={isRunning}
        />
        <MetricCard
          label="Answer Correctness"
          value={formatMetric(results?.answer_correctness)}
          isLoading={isRunning}
        />
      </div>

      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Button onClick={() => void runEvaluation()} disabled={isRunning} className="gap-2">
            {isRunning ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Run Evaluation
          </Button>
          {results && (
            <span className="text-sm text-muted-foreground">
              Evaluated {results.total_records} records
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setLimit(10)} disabled={limit === 10}>
            10
          </Button>
          <Button variant="outline" size="sm" onClick={() => setLimit(20)} disabled={limit === 20}>
            20
          </Button>
          <Button variant="outline" size="sm" onClick={() => setLimit(50)} disabled={limit === 50}>
            50
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive" className="shrink-0">
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}

      <Card className="flex-1 min-h-0 overflow-hidden flex flex-col">
        <CardHeader className="shrink-0 pb-2">
          <CardTitle className="text-base">Golden Dataset</CardTitle>
          <CardDescription>
            Showing {records.length} of {total} records
          </CardDescription>
        </CardHeader>
        <CardContent className="flex-1 min-h-0 overflow-auto p-0">
          {isLoading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-muted sticky top-0 z-10">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Query</th>
                  <th className="text-left px-4 py-2 font-medium w-32">Intent</th>
                  <th className="text-left px-4 py-2 font-medium w-40">Slots</th>
                  <th className="text-left px-4 py-2 font-medium w-40">Answer Fragment</th>
                  <th className="text-left px-4 py-2 font-medium w-28">Audit Level</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {records.map((record, idx) => (
                  <tr key={idx} className="hover:bg-muted/50">
                    <td className="px-4 py-2 max-w-md truncate" title={record.query}>
                      {record.query}
                    </td>
                    <td className="px-4 py-2">
                      <Badge variant="outline">{record.expected_intent}</Badge>
                    </td>
                    <td className="px-4 py-2">
                      {Object.keys(record.expected_slots || {}).length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {Object.entries(record.expected_slots || {}).map(([k, v]) => (
                            <Badge key={k} variant="secondary" className="text-xs">
                              {k}: {v}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2 truncate" title={record.expected_answer_fragment}>
                      {record.expected_answer_fragment}
                    </td>
                    <td className="px-4 py-2">
                      <AuditLevelBadge level={record.expected_audit_level} />
                    </td>
                  </tr>
                ))}
                {records.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                      No records found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </CardContent>
        <div className="flex items-center justify-between px-4 py-3 border-t shrink-0">
          <div className="text-sm text-muted-foreground">
            Offset {offset} — {Math.min(offset + limit, total)} of {total}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePrev}
              disabled={offset === 0 || isLoading}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Prev
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleNext}
              disabled={offset + limit >= total || isLoading}
            >
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

function MetricCard({
  label,
  value,
  isLoading,
}: {
  label: string
  value: string
  isLoading: boolean
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription className="text-xs">{label}</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-6 w-20" />
        ) : (
          <CardTitle className="text-2xl">{value}</CardTitle>
        )}
      </CardContent>
    </Card>
  )
}

function AuditLevelBadge({ level }: { level?: string }) {
  if (!level) return <span className="text-muted-foreground">—</span>
  const variantMap: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
    auto: 'default',
    medium: 'secondary',
    manual: 'destructive',
  }
  return (
    <Badge variant={variantMap[level] || 'outline'} className="capitalize">
      {level}
    </Badge>
  )
}
