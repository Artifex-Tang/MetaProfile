import { describe, it, expect } from 'vitest'
import { isNavType, parseFromQuery, NAV_TYPES } from './crossProfile'

describe('NAV_TYPES', () => {
  it('集合恰为四类画像（小写）', () => {
    expect(NAV_TYPES).toEqual(new Set(['tech', 'project', 'org', 'person']))
  })
})

describe('isNavType', () => {
  it('接受四类画像（小写）', () => {
    expect(isNavType('person')).toBe(true)
    expect(isNavType('org')).toBe(true)
    expect(isNavType('project')).toBe(true)
    expect(isNavType('tech')).toBe(true)
  })

  it('后端大写 EntityType 经归一化后仍命中', () => {
    expect(isNavType('PERSON')).toBe(true)
    expect(isNavType('Org')).toBe(true)
    expect(isNavType('PROJECT')).toBe(true)
  })

  it('扩展/未知/空类型不命中', () => {
    expect(isNavType('enterprise')).toBe(false)
    expect(isNavType('strategy')).toBe(false)
    expect(isNavType('unknown')).toBe(false)
    expect(isNavType('')).toBe(false)
    expect(isNavType(null)).toBe(false)
    expect(isNavType(undefined)).toBe(false)
  })
})

describe('parseFromQuery', () => {
  it('正常解析 type:id', () => {
    expect(parseFromQuery('?from=person:PERSON_20260101_abcd1234')).toEqual({
      fromType: 'person',
      fromId: 'PERSON_20260101_abcd1234',
    })
  })

  it('接受裸 search 串（不带前导 ?）', () => {
    expect(parseFromQuery('from=org:ORG_1')).toEqual({ fromType: 'org', fromId: 'ORG_1' })
  })

  it('无 from 参数返回 null', () => {
    expect(parseFromQuery('')).toBeNull()
    expect(parseFromQuery('?foo=bar')).toBeNull()
  })

  it('缺冒号返回 null', () => {
    expect(parseFromQuery('?from=persononly')).toBeNull()
  })

  it('冒号在首位（缺类型）返回 null', () => {
    expect(parseFromQuery('?from=:id')).toBeNull()
  })

  it('对 id 中的特殊字符做 URL 解码', () => {
    // id 含空格，已被 encodeURIComponent 编码为 %20
    expect(parseFromQuery('?from=org:name%20with%20space')).toEqual({
      fromType: 'org',
      fromId: 'name with space',
    })
  })
})
