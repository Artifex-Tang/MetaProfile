import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import EntityName from './EntityName'

describe('EntityName', () => {
  it('已译(name_cn 有) → 只显 name，无翻译按钮', () => {
    render(<EntityName entity={{ name_cn: '量子', name_en: 'q', id: 'T1' }} />)
    expect(screen.getByText('量子')).toBeInTheDocument()
    expect(screen.queryByText('译')).not.toBeInTheDocument()
  })

  it('未译 + onTranslate → 显 name_en + 译按钮', () => {
    render(<EntityName entity={{ name_cn: '', name_en: 'quantum', id: 'T1' }} onTranslate={() => {}} />)
    expect(screen.getByText('quantum')).toBeInTheDocument()
    expect(screen.getByText('译')).toBeInTheDocument()
  })

  it('未译但无 onTranslate → 只显名(探索页/网络节点场景)', () => {
    render(<EntityName entity={{ name_cn: '', name_en: 'quantum', id: 'T1' }} />)
    expect(screen.getByText('quantum')).toBeInTheDocument()
    expect(screen.queryByText('译')).not.toBeInTheDocument()
  })

  it('点译按钮 → 调 onTranslate', () => {
    const onTranslate = vi.fn()
    render(<EntityName entity={{ name_cn: '', name_en: 'q', id: 'T1' }} onTranslate={onTranslate} />)
    fireEvent.click(screen.getByText('译'))
    expect(onTranslate).toHaveBeenCalledTimes(1)
  })

  it('都空 → 显 id', () => {
    render(<EntityName entity={{ name_cn: '', name_en: '', id: 'T9' }} />)
    expect(screen.getByText('T9')).toBeInTheDocument()
  })
})
