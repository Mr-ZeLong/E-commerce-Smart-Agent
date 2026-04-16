import { describe, expect, it } from 'vitest'
import { riskLevelConfig } from './risk'

describe('riskLevelConfig', () => {
  it('has HIGH risk config', () => {
    expect(riskLevelConfig.HIGH.label).toBe('高风险')
    expect(riskLevelConfig.HIGH.className).toContain('bg-red-100')
  })

  it('has MEDIUM risk config', () => {
    expect(riskLevelConfig.MEDIUM.label).toBe('中风险')
    expect(riskLevelConfig.MEDIUM.className).toContain('bg-yellow-100')
  })

  it('has LOW risk config', () => {
    expect(riskLevelConfig.LOW.label).toBe('低风险')
    expect(riskLevelConfig.LOW.className).toContain('bg-green-100')
  })
})
