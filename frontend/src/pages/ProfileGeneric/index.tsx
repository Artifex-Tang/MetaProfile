import { useState } from 'react'
import {
  Input, Button, Table, Tag, Drawer, Spin, Alert,
  Space, Typography, Descriptions, message, Form, Upload,
} from 'antd'
import { SearchOutlined, ReloadOutlined, UploadOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

const { Search } = Input
const { Text } = Typography

type ProfileService = {
  search: (k: string, page?: number, ps?: number) => Promise<{ items: Record<string, unknown>[]; total: number }>
  getById: (id: string) => Promise<Record<string, unknown>>
  bulkImport: (p: Record<string, unknown>[]) => Promise<unknown>
  getStats: () => Promise<{ total?: number }>
}

function DetailDrawer({
  service, entityKey, id, open, onClose,
}: {
  service: ProfileService; entityKey: string; id: string; open: boolean; onClose: () => void
}) {
  const profile = useQuery({
    queryKey: [entityKey, id],
    queryFn: () => service.getById(id),
    enabled: open && !!id,
  })
  const p = profile.data

  const nameKey = Object.keys(p ?? {}).find(k => k.includes('name_cn') || k.includes('name') || k.endsWith('_name')) ?? ''
  const title = p ? (p[nameKey] as string ?? id) : id

  return (
    <Drawer title={title} width={560} open={open} onClose={onClose} destroyOnClose>
      {profile.isLoading ? <Spin /> : profile.isError ? <Alert type="error" message="加载失败" /> : p && (
        <Descriptions column={1} size="small" bordered>
          {Object.entries(p).map(([k, v]) => (
            <Descriptions.Item key={k} label={k}>
              {Array.isArray(v)
                ? v.map((x, i) => <Tag key={i}>{typeof x === 'string' ? x : JSON.stringify(x)}</Tag>)
                : typeof v === 'object' && v !== null
                  ? <Text code style={{ fontSize: 11 }}>{JSON.stringify(v, null, 2)}</Text>
                  : String(v ?? '-')}
            </Descriptions.Item>
          ))}
        </Descriptions>
      )}
    </Drawer>
  )
}

export function GenericProfilePage({
  service, entityKey, idField, nameField, label,
}: {
  service: ProfileService
  entityKey: string
  idField: string
  nameField: string
  label: string
}) {
  const qc = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: [entityKey + '-search', keyword, page],
    queryFn: () => service.search(keyword, page, 20),
  })

  const importMut = useMutation({
    mutationFn: (profiles: Record<string, unknown>[]) => service.bulkImport(profiles),
    onSuccess: () => {
      message.success('导入成功')
      qc.invalidateQueries({ queryKey: [entityKey + '-search'] })
    },
    onError: () => message.error('导入失败'),
  })

  const rows = data?.items ?? []
  const extraKeys = rows.length > 0
    ? Object.keys(rows[0]).filter(k => k !== idField && k !== nameField).slice(0, 3)
    : []

  const cols = [
    { title: 'ID', dataIndex: idField, width: 180, ellipsis: true },
    { title: '名称', dataIndex: nameField, ellipsis: true },
    ...extraKeys.map(k => ({
      title: k,
      dataIndex: k,
      ellipsis: true,
      render: (v: unknown) => Array.isArray(v) ? v.slice(0, 2).join(', ') : String(v ?? '-'),
    })),
    {
      title: '操作',
      width: 80,
      render: (_: unknown, r: Record<string, unknown>) => (
        <Button type="link" size="small" onClick={() => setSelectedId(r[idField] as string)}>详情</Button>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Search
          placeholder={`搜索${label}名称`}
          allowClear
          style={{ width: 280 }}
          onSearch={v => { setKeyword(v); setPage(1) }}
          enterButton={<SearchOutlined />}
        />
        <Upload
          accept=".json"
          showUploadList={false}
          beforeUpload={file => {
            const reader = new FileReader()
            reader.onload = e => {
              try {
                const arr = JSON.parse(e.target?.result as string)
                importMut.mutate(Array.isArray(arr) ? arr : [arr])
              } catch {
                message.error('JSON 解析失败')
              }
            }
            reader.readAsText(file)
            return false
          }}
        >
          <Button icon={<UploadOutlined />} loading={importMut.isPending}>批量导入</Button>
        </Upload>
        <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
      </Space>

      {isError && <Alert type="error" message="搜索失败" style={{ marginBottom: 16 }} />}

      <Table
        loading={isLoading}
        dataSource={rows}
        columns={cols}
        rowKey={idField}
        size="small"
        pagination={{
          current: page,
          pageSize: 20,
          total: data?.total,
          onChange: p => setPage(p),
          showTotal: t => `共 ${t} 条`,
        }}
        onRow={r => ({ onDoubleClick: () => setSelectedId(r[idField] as string) })}
      />

      {selectedId && (
        <DetailDrawer
          service={service}
          entityKey={entityKey}
          id={selectedId}
          open={!!selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  )
}
