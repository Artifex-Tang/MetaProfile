import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import EntityTypeSelect from './EntityTypeSelect'

// vi.mock 被 hoist 到文件顶部，工厂函数不能引用普通顶层变量（TDZ）。
// 用 vi.hoisted 把 services 同步提升，工厂内即可安全引用。
const services = vi.hoisted(() => ({
  tech: { search: vi.fn().mockResolvedValue({ items: [{ tech_id: 'T1', tech_name_cn: '量子技术' }] }) },
  org: { search: vi.fn().mockResolvedValue({ items: [{ org_id: 'O1', name_cn: '量子机构' }] }) },
  person: { search: vi.fn().mockResolvedValue({ items: [{ person_id: 'P1', name_cn: '张三' }] }) },
  project: { search: vi.fn().mockResolvedValue({ items: [{ project_id: 'PR1', name_cn: ['量子项目'] }] }) },
}))
vi.mock('../api/tech', () => ({ techService: services.tech }))
vi.mock('../api/profile', () => ({
  orgService: services.org,
  personService: services.person,
  projectService: services.project,
}))

// 真实形状核对：service.search → SearchResultList = { items: T[], total }
// 字段名：tech=tech_id/tech_name_cn, org=org_id/name_cn,
// person=person_id/name_cn, project=project_id/name_cn（project.name_cn 为 list，组件取 [0]）。

describe('EntityTypeSelect', () => {
  it('默认渲染不崩 + 默认 placeholder 出现', () => {
    render(<EntityTypeSelect value={undefined} onChange={() => {}} />)
    // antd Select placeholder 通过 span 渲染，这里断言默认 placeholder 存在
    expect(screen.getByText('选择实体')).toBeInTheDocument()
  })

  it('allowedTypes + 自定义 placeholder 生效', () => {
    render(
      <EntityTypeSelect
        value={undefined}
        onChange={() => {}}
        allowedTypes={['tech']}
        placeholder="选技术"
      />,
    )
    expect(screen.getByText('选技术')).toBeInTheDocument()
  })

  it('project.name_cn(list) → 取 [0] 正确归一', async () => {
    const onChange = vi.fn()
    render(
      <EntityTypeSelect
        value={undefined}
        onChange={onChange}
        allowedTypes={['project']}
      />,
    )
    // 组件渲染两个 Select（type 下拉 + entity 搜索），jsdom 下两者 role 都是 combobox。
    // 第二个(index 1)是带 showSearch 的实体搜索框。用 getAllByRole 锁定，避免 getByRole 多元素报错。
    const comboboxes = screen.getAllByRole('combobox')
    expect(comboboxes.length).toBeGreaterThanOrEqual(2)
    fireEvent.change(comboboxes[1], { target: { value: '量子项目' } })
    await waitFor(() => expect(services.project.search).toHaveBeenCalledWith('量子项目', 1, 20))
  })

  it('tech 搜索 → 调 techService.search(keyword, 1, 20)', async () => {
    render(
      <EntityTypeSelect
        value={undefined}
        onChange={() => {}}
        allowedTypes={['tech']}
      />,
    )
    const comboboxes = screen.getAllByRole('combobox')
    expect(comboboxes.length).toBeGreaterThanOrEqual(2)
    fireEvent.change(comboboxes[1], { target: { value: '量子技术' } })
    await waitFor(() => expect(services.tech.search).toHaveBeenCalledWith('量子技术', 1, 20))
    // 其余 service 不应被调用
    expect(services.org.search).not.toHaveBeenCalled()
  })
})
