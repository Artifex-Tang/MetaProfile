import { describe, it, expect } from 'vitest'
import { displayName, isUntranslated } from './displayName'

describe('displayName', () => {
  it('name_cn 优先', () => {
    expect(displayName({ name_cn: '量子', name_en: 'q', id: 'T1' })).toBe('量子')
  })
  it('name_cn 空回退 name_en', () => {
    expect(displayName({ name_cn: '', name_en: 'quantum', id: 'T1' })).toBe('quantum')
  })
  it('都空回退 id', () => {
    expect(displayName({ name_cn: '', name_en: '', id: 'T1' })).toBe('T1')
  })
  it('null 安全', () => {
    expect(displayName({ name_cn: null, name_en: null, id: 'X' })).toBe('X')
  })
  it('空白串当空', () => {
    expect(displayName({ name_cn: '   ', name_en: 'q', id: 'T1' })).toBe('q')
  })
})

describe('isUntranslated', () => {
  it('name_cn 空 & name_en 有 → true', () => {
    expect(isUntranslated({ name_cn: '', name_en: 'q', id: 'T1' })).toBe(true)
  })
  it('name_cn 有 → false', () => {
    expect(isUntranslated({ name_cn: '量', name_en: 'q', id: 'T1' })).toBe(false)
  })
  it('都空 → false（无源可译）', () => {
    expect(isUntranslated({ name_cn: '', name_en: '', id: 'T1' })).toBe(false)
  })
})
