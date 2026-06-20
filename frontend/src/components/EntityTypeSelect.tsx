import { useState } from 'react'
import { Select } from 'antd'
import { techService } from '../api/tech'
import { orgService, personService, projectService } from '../api/profile'

export interface EntitySel {
  type: string
  id: string
  name: string
}

const TYPE_LABELS: { type: string; label: string }[] = [
  { type: 'tech', label: '技术' },
  { type: 'project', label: '项目' },
  { type: 'org', label: '机构' },
  { type: 'person', label: '人员' },
]

// type → (service, idKey, nameKey, nameIsList)
// 真实 SearchItem 字段名：tech=tech_id/tech_name_cn, org=org_id/name_cn,
// person=person_id/name_cn, project=project_id/name_cn(后者为 list, 取 [0])
interface SrvEntry {
  search: (k: string, p?: number, s?: number) => Promise<{ items: any[]; total?: number }>
  idKey: string
  nameKey: string
  nameIsList?: boolean
}
const SRV: Record<string, SrvEntry> = {
  tech: { search: (k, p, s) => techService.search(k, p, s), idKey: 'tech_id', nameKey: 'tech_name_cn' },
  org: { search: (k, p, s) => orgService.search(k, p, s), idKey: 'org_id', nameKey: 'name_cn' },
  person: { search: (k, p, s) => personService.search(k, p, s), idKey: 'person_id', nameKey: 'name_cn' },
  project: { search: (k, p, s) => projectService.search(k, p, s), idKey: 'project_id', nameKey: 'name_cn', nameIsList: true },
}

export default function EntityTypeSelect({
  value,
  onChange,
  allowedTypes,
  placeholder = '选择实体',
}: {
  value?: EntitySel | null
  onChange: (v: EntitySel | null) => void
  allowedTypes?: string[]
  placeholder?: string
}) {
  const types = allowedTypes ?? TYPE_LABELS.map((t) => t.type)
  const [type, setType] = useState<string>(value?.type ?? types[0])
  const [opts, setOpts] = useState<{ id: string; name: string }[]>([])
  const [kw, setKw] = useState('')

  const doSearch = async (key: string) => {
    const srv = SRV[type]
    if (!srv || !key.trim()) {
      setOpts([])
      return
    }
    try {
      const res = await srv.search(key.trim(), 1, 20)
      setOpts(
        (res.items ?? []).map((it) => {
          let nm: any = it[srv.nameKey]
          if (srv.nameIsList && Array.isArray(nm)) nm = nm[0]
          return { id: it[srv.idKey], name: nm ?? it[srv.idKey] }
        }),
      )
    } catch {
      setOpts([])
    }
  }

  return (
    <span style={{ display: 'inline-flex', gap: 8 }}>
      <Select
        size="small"
        style={{ width: 90 }}
        value={type}
        options={TYPE_LABELS.filter((t) => types.includes(t.type))}
        // TYPE_LABELS 是 {type,label} 结构，antd Select 默认取 {value,label}，
        // 必须显式 fieldNames 让 value 字段指向 'type'，否则下拉值无法选中。
        fieldNames={{ label: 'label', value: 'type' }}
        onChange={(t) => {
          setType(t)
          setOpts([])
          onChange(null)
        }}
      />
      <Select
        size="small"
        style={{ width: 220 }}
        showSearch
        value={value?.id}
        placeholder={placeholder}
        filterOption={false}
        options={opts.map((o) => ({ value: o.id, label: o.name }))}
        onSearch={(v) => {
          setKw(v)
          doSearch(v)
        }}
        notFoundContent={kw ? '无匹配实体' : undefined}
        onChange={(id) => {
          const o = opts.find((x) => x.id === id) ?? null
          onChange(o ? { type, id: o.id, name: o.name } : null)
        }}
      />
    </span>
  )
}
