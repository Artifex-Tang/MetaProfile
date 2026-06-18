import { describe, it, expect } from 'vitest'
import { enrichStatusLabel, isEnrichTerminal } from './enrichStatus'

describe('enrichStatus', () => {
  it('maps known statuses to Chinese labels', () => {
    expect(enrichStatusLabel('queued')).toBe('排队中')
    expect(enrichStatusLabel('pending')).toBe('执行中')
    expect(enrichStatusLabel('done')).toBe('已完成')
    expect(enrichStatusLabel('skipped')).toBe('无需补全')
    expect(enrichStatusLabel('failed')).toBe('失败')
    expect(enrichStatusLabel('error')).toBe('出错')
    expect(enrichStatusLabel('no_fill')).toBe('无字段可补')
  })

  it('returns 未知 for unknown/undefined', () => {
    expect(enrichStatusLabel(undefined)).toBe('未知')
    expect(enrichStatusLabel('whatever')).toBe('未知')
  })

  it('flags terminal statuses', () => {
    expect(isEnrichTerminal('done')).toBe(true)
    expect(isEnrichTerminal('skipped')).toBe(true)
    expect(isEnrichTerminal('failed')).toBe(true)
    expect(isEnrichTerminal('error')).toBe(true)
    expect(isEnrichTerminal('no_fill')).toBe(true)
    expect(isEnrichTerminal('pending')).toBe(false)
    expect(isEnrichTerminal('queued')).toBe(false)
    expect(isEnrichTerminal(undefined)).toBe(false)
  })
})
