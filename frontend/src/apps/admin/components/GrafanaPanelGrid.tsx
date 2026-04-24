import type { ElementType } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { GrafanaEmbed } from './GrafanaEmbed'
import { BarChart3, Gauge, DollarSign, ShieldCheck } from 'lucide-react'

export interface DashboardConfig {
  uid: string
  title: string
  icon: ElementType
}

export interface GrafanaPanelGridProps {
  timeRangeFrom?: string
  timeRangeTo?: string
  theme?: 'light' | 'dark'
}

const dashboards: DashboardConfig[] = [
  { uid: 'ecommerce-agent', title: '系统概览', icon: BarChart3 },
  { uid: 'agent-performance', title: '性能监控', icon: Gauge },
  { uid: 'cost-optimization', title: '成本优化', icon: DollarSign },
  { uid: 'security-monitoring', title: '安全监控', icon: ShieldCheck },
]

export function GrafanaPanelGrid({
  timeRangeFrom = 'now-24h',
  timeRangeTo = 'now',
  theme = 'light',
}: GrafanaPanelGridProps) {
  return (
    <Tabs defaultValue={dashboards[0].uid} className="w-full space-y-4">
      <TabsList className="w-full justify-start overflow-x-auto">
        {dashboards.map((db) => (
          <TabsTrigger key={db.uid} value={db.uid} className="gap-2">
            <db.icon className="h-4 w-4" />
            {db.title}
          </TabsTrigger>
        ))}
      </TabsList>

      {dashboards.map((db) => (
        <TabsContent key={db.uid} value={db.uid} className="mt-4">
          <GrafanaEmbed
            dashboardUid={db.uid}
            height="700px"
            timeRangeFrom={timeRangeFrom}
            timeRangeTo={timeRangeTo}
            theme={theme}
          />
        </TabsContent>
      ))}
    </Tabs>
  )
}

export default GrafanaPanelGrid
