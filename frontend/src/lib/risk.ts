export const riskLevelConfig = {
  HIGH: { className: 'bg-red-100 text-red-800', label: '高风险' },
  MEDIUM: { className: 'bg-yellow-100 text-yellow-800', label: '中风险' },
  LOW: { className: 'bg-green-100 text-green-800', label: '低风险' },
} as const

export type RiskLevel = keyof typeof riskLevelConfig
