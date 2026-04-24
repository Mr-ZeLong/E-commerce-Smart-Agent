import { onCLS, onFID, onLCP, onFCP, onTTFB } from 'web-vitals'
import type { CLSMetric, FIDMetric, LCPMetric, FCPMetric, TTFBMetric } from 'web-vitals'

interface WebVitalsConfig {
  samplingRate?: number
  endpoint?: string
  context?: Record<string, string>
}

interface WebVitalsPayload {
  metric: string
  value: number
  rating: 'good' | 'needs-improvement' | 'poor'
  url: string
  user_agent: string
  timestamp: string
  [key: string]: string | number
}

const DEFAULT_ENDPOINT = '/api/v1/metrics/web-vitals'

function sendMetric(payload: WebVitalsPayload, endpoint: string): void {
  void fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    keepalive: true,
  }).catch(() => undefined)
}

function buildPayload(
  metricName: string,
  value: number,
  rating: 'good' | 'needs-improvement' | 'poor',
  context?: Record<string, string>
): WebVitalsPayload {
  // web-vitals reports LCP, FID, FCP, TTFB in milliseconds
  // CLS is unitless (score between 0 and 1)
  const isMsMetric = ['LCP', 'FID', 'FCP', 'TTFB'].includes(metricName)
  const normalizedValue = isMsMetric ? value / 1000 : value
  return {
    metric: metricName,
    value: Math.round(normalizedValue * 1000) / 1000,
    rating,
    url: window.location.href,
    user_agent: navigator.userAgent,
    timestamp: new Date().toISOString(),
    ...context,
  }
}

export function initWebVitals(config: WebVitalsConfig = {}): void {
  const { samplingRate = 0.1, endpoint = DEFAULT_ENDPOINT, context = {} } = config

  if (Math.random() > samplingRate) {
    return
  }

  onCLS((metric: CLSMetric) => {
    void sendMetric(buildPayload('CLS', metric.value, metric.rating, context), endpoint)
  }, { reportAllChanges: false })

  onFID((metric: FIDMetric) => {
    void sendMetric(buildPayload('FID', metric.value, metric.rating, context), endpoint)
  })

  onLCP((metric: LCPMetric) => {
    void sendMetric(buildPayload('LCP', metric.value, metric.rating, context), endpoint)
  }, { reportAllChanges: false })

  onFCP((metric: FCPMetric) => {
    void sendMetric(buildPayload('FCP', metric.value, metric.rating, context), endpoint)
  })

  onTTFB((metric: TTFBMetric) => {
    void sendMetric(buildPayload('TTFB', metric.value, metric.rating, context), endpoint)
  })
}
