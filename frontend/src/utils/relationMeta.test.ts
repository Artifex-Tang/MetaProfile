import { describe, it, expect } from 'vitest'
import { relLabel, TYPE_META, metaOf } from './relationMeta'

describe('relLabel', () => {
  it('TECH_EVOLVE → 演进', () => expect(relLabel('TECH_EVOLVE')).toBe('演进'))
  it('TECH_PREREQ → 前置', () => expect(relLabel('TECH_PREREQ')).toBe('前置'))
  it('中文键原样', () => expect(relLabel('演进')).toBe('演进'))
  it('既有英文枚举仍工作', () => expect(relLabel('ORG_FUND')).toBe('拨款/资助'))
  it('未知透传', () => expect(relLabel('XX')).toBe('XX'))
  it('空→空串', () => expect(relLabel(null)).toBe(''))
})

describe('TYPE_META / metaOf', () => {
  it('tech 着色', () => {
    expect(TYPE_META.tech.color).toBeTruthy()
    expect(metaOf('tech').label).toBe('技术')
  })
  it('未知类型兜底', () => {
    expect(metaOf('unknown_xyz').label).toBe('unknown_xyz')
  })
})
