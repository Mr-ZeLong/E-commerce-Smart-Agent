import { useState, useMemo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle } from 'lucide-react'

export interface GrafanaEmbedProps {
  dashboardUid: string
  panelId?: number
  height?: string
  timeRangeFrom?: string
  timeRangeTo?: string
  theme?: 'light' | 'dark'
  extraParams?: Record<string, string>
}

function buildGrafanaUrl(
  baseUrl: string,
  dashboardUid: string,
  options: {
    panelId?: number
    timeRangeFrom?: string
    timeRangeTo?: string
    theme?: 'light' | 'dark'
    extraParams?: Record<string, string>
  }
): string {
  const params = new URLSearchParams()
  params.set('kiosk', '')
  params.set('theme', options.theme ?? 'light')
  params.set('from', options.timeRangeFrom ?? 'now-24h')
  params.set('to', options.timeRangeTo ?? 'now')

  if (options.panelId !== undefined) {
    params.set('viewPanel', options.panelId.toString())
  }

  if (options.extraParams) {
    Object.entries(options.extraParams).forEach(([key, value]) => {
      params.set(key, value)
    })
  }

  const path = options.panelId !== undefined ? 'd-solo' : 'd'
  return `${baseUrl}/${path}/${dashboardUid}?${params.toString()}`
}

export function GrafanaEmbed({
  dashboardUid,
  panelId,
  height = '600px',
  timeRangeFrom = 'now-24h',
  timeRangeTo = 'now',
  theme = 'light',
  extraParams,
}: GrafanaEmbedProps) {
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)

  const grafanaUrl = import.meta.env.VITE_GRAFANA_URL ?? 'http://localhost:3000'

  const src = useMemo(
    () =>
      buildGrafanaUrl(grafanaUrl, dashboardUid, {
        panelId,
        timeRangeFrom,
        timeRangeTo,
        theme,
        extraParams,
      }),
    [grafanaUrl, dashboardUid, panelId, timeRangeFrom, timeRangeTo, theme, extraParams]
  )

  const handleLoad = (): void => {
    setIsLoading(false)
    setHasError(false)
  }

  const handleError = (): void => {
    setIsLoading(false)
    setHasError(true)
  }

  if (hasError) {
    return (
      <Card className="w-full" style={{ height }}>
        <CardContent className="flex flex-col items-center justify-center h-full gap-4">
          <AlertCircle className="h-12 w-12 text-destructive" />
          <div className="text-center">
            <p className="text-lg font-medium text-destructive">无法加载 Grafana 仪表板</p>
            <p className="text-sm text-muted-foreground mt-1">
              请检查 Grafana 服务是否正常运行 ({grafanaUrl})
            </p>
            <p className="text-xs text-muted-foreground mt-2">
              Dashboard UID: {dashboardUid}
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="relative w-full" style={{ height }}>
      {isLoading && (
        <div className="absolute inset-0 z-10">
          <Card className="w-full h-full">
            <CardContent className="flex flex-col gap-4 p-6">
              <Skeleton className="h-8 w-1/3" />
              <Skeleton className="h-4 w-1/4" />
              <div className="flex-1 grid grid-cols-3 gap-4 mt-4">
                <Skeleton className="h-full" />
                <Skeleton className="h-full" />
                <Skeleton className="h-full" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}
      <iframe
        src={src}
        width="100%"
        height="100%"
        frameBorder="0"
        sandbox="allow-same-origin allow-scripts"
        title={`Grafana Dashboard ${dashboardUid}`}
        onLoad={handleLoad}
        onError={handleError}
        className="rounded-md"
      />
    </div>
  )
}

export default GrafanaEmbed
