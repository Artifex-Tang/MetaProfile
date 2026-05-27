import { useState, useRef, useEffect } from 'react'
import {
  Input, Button, Table, Tag, Drawer, Tabs, Spin, Alert,
  Descriptions, Space, Typography, Upload, message, Timeline, Card,
} from 'antd'
import { SearchOutlined, ReloadOutlined, UploadOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectService } from '../../api/profile'
import type { ProjectProfile, ProjectSearchItem, RelationItem } from '../../api/types'
import G6 from '@antv/g6'

const { Search } = Input
const { Text } = Typography

const ENTITY_NODE_COLOR: Record<string, string> = {
  tech: '#1677ff',
  org: '#52c41a',
  person: '#fa8c16',
  enterprise: '#722ed1',
}

function RelationGraph({ relations }: { relations: RelationItem[] }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current) return
    const selfNode = { id: '_self', label: '当前项目', style: { fill: '#1677ff', stroke: '#1677ff' } }
    const targetNodes = relations.map(r => ({
      id: r.target_entity_id,
      label: r.target_name ?? r.target_entity_id.slice(0, 8),
      style: { fill: ENTITY_NODE_COLOR[r.target_entity_type] ?? '#999', stroke: ENTITY_NODE_COLOR[r.target_entity_type] ?? '#999' },
    }))
    const edges = relations.map((r, i) => ({ id: `e${i}`, source: '_self', target: r.target_entity_id, label: r.relation_type }))
    const graph = new G6.Graph({
      container: ref.current,
      width: ref.current.clientWidth || 500,
      height: 320,
      fitView: true,
      layout: { type: 'radial', unitRadius: 130 },
      defaultNode: { size: 36, labelCfg: { position: 'bottom', style: { fontSize: 11 } }, style: { fill: '#ccc' } },
      defaultEdge: { labelCfg: { style: { fontSize: 10, fill: '#666' } } },
      modes: { default: ['drag-canvas', 'zoom-canvas', 'drag-node'] },
    })
    graph.data({ nodes: [selfNode, ...targetNodes], edges })
    graph.render()
    return () => { graph.destroy() }
  }, [relations])

  return <div ref={ref} style={{ width: '100%', height: 320, background: '#fafafa', borderRadius: 4 }} />
}

function DetailDrawer({ id, open, onClose }: { id: string; open: boolean; onClose: () => void }) {
  const profile = useQuery({
    queryKey: ['project', id],
    queryFn: () => projectService.getById(id),
    enabled: open && !!id,
  })
  const relations = useQuery({
    queryKey: ['project-relations', id],
    queryFn: () => projectService.getRelations(id),
    enabled: open && !!id,
  })
  const p = profile.data

  const primaryName = p?.name_cn?.[0] ?? id

  return (
    <Drawer title={primaryName} width={700} open={open} onClose={onClose} destroyOnClose>
      {profile.isLoading ? <Spin /> : profile.isError ? <Alert type="error" message="加载失败" /> : p && (
        <Tabs items={[
          {
            key: 'info', label: '基本信息',
            children: (
              <Descriptions column={1} size="small" bordered>
                <Descriptions.Item label="项目名称（中）">
                  {p.name_cn.map((n, i) => <div key={i}>{n}</div>)}
                </Descriptions.Item>
                {p.name_en.length > 0 && (
                  <Descriptions.Item label="项目名称（英）">
                    {p.name_en.map((n, i) => <div key={i}>{n}</div>)}
                  </Descriptions.Item>
                )}
                <Descriptions.Item label="技术领域">
                  {p.tech_domain.map(d => <Tag key={d}>{d}</Tag>)}
                </Descriptions.Item>
                <Descriptions.Item label="启动时间">{p.start_date ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="完成时间">{p.finish_date ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="状态">
                  {p.status.map(s => <Tag key={s} color="blue">{s}</Tag>)}
                </Descriptions.Item>
                <Descriptions.Item label="主管机构">
                  {p.main_orgs.map(o => <Tag key={o}>{o}</Tag>)}
                </Descriptions.Item>
                {p.undertaking_orgs.length > 0 && (
                  <Descriptions.Item label="承研机构">
                    {p.undertaking_orgs.map(o => <Tag key={o}>{o}</Tag>)}
                  </Descriptions.Item>
                )}
                {p.managers.length > 0 && (
                  <Descriptions.Item label="项目负责人">
                    {p.managers.map(m => <Tag key={m}>{m}</Tag>)}
                  </Descriptions.Item>
                )}
                {p.researchers.length > 0 && (
                  <Descriptions.Item label="研究人员">
                    {p.researchers.slice(0, 6).map(r => <Tag key={r}>{r}</Tag>)}
                    {p.researchers.length > 6 && <Tag>+{p.researchers.length - 6} 人</Tag>}
                  </Descriptions.Item>
                )}
                {p.total_budget_million_usd != null && (
                  <Descriptions.Item label="总预算（百万美元）">{p.total_budget_million_usd.toFixed(2)}</Descriptions.Item>
                )}
                {p.invested_million_usd != null && (
                  <Descriptions.Item label="已投入（百万美元）">{p.invested_million_usd.toFixed(2)}</Descriptions.Item>
                )}
                {p.research_goal && (
                  <Descriptions.Item label="研究目标">
                    <Text style={{ whiteSpace: 'pre-wrap' }}>{p.research_goal}</Text>
                  </Descriptions.Item>
                )}
                {p.keywords.length > 0 && (
                  <Descriptions.Item label="关键词">
                    {p.keywords.map(k => <Tag key={k} color="purple">{k}</Tag>)}
                  </Descriptions.Item>
                )}
                <Descriptions.Item label="置信度">{(p.confidence * 100).toFixed(1)}%</Descriptions.Item>
              </Descriptions>
            ),
          },
          {
            key: 'content', label: '研究内容',
            children: (
              <Space direction="vertical" style={{ width: '100%' }} size={12}>
                {p.research_content.length > 0 && (
                  <Card title="主要研究内容" size="small">
                    <ul style={{ paddingLeft: 20, margin: 0 }}>
                      {p.research_content.map((c, i) => <li key={i} style={{ marginBottom: 4 }}>{c}</li>)}
                    </ul>
                  </Card>
                )}
                {p.progress.length > 0 && (
                  <Card title="主要进展" size="small">
                    <ul style={{ paddingLeft: 20, margin: 0 }}>
                      {p.progress.map((pg, i) => <li key={i} style={{ marginBottom: 4 }}>{pg}</li>)}
                    </ul>
                  </Card>
                )}
              </Space>
            ),
          },
          {
            key: 'history', label: `发展历程 (${p.histories.length})`,
            children: p.histories.length === 0
              ? <Text type="secondary">暂无历程数据</Text>
              : (
                <Timeline
                  mode="left"
                  items={p.histories.map((h, i) => ({
                    key: i,
                    label: h.change_date ?? '-',
                    children: <Text>{h.change_description ?? '-'}</Text>,
                  }))}
                />
              ),
          },
          {
            key: 'budget', label: `预算 (${p.budgets.length})`,
            children: p.budgets.length === 0
              ? <Text type="secondary">暂无预算数据</Text>
              : (
                <Table
                  size="small"
                  dataSource={p.budgets}
                  rowKey={(_, i) => String(i)}
                  pagination={false}
                  columns={[
                    { title: '预算日期', dataIndex: 'budget_date', width: 130, render: v => v ?? '-' },
                    { title: '金额（百万美元）', dataIndex: 'amount', render: (v: number) => v.toFixed(2) },
                  ]}
                />
              ),
          },
          {
            key: 'outputs', label: `项目成果 (${p.outputs.length})`,
            children: p.outputs.length === 0
              ? <Text type="secondary">暂无成果数据</Text>
              : p.outputs.map((o, i) => (
                <Card key={i} size="small" style={{ marginBottom: 8 }}>
                  <div><Text strong>{o.name_history ?? `成果 ${i + 1}`}</Text></div>
                  {o.formed_at && <div style={{ color: '#595959', fontSize: 12 }}>形成时间: {o.formed_at}</div>}
                  {o.tech_domains.length > 0 && (
                    <div style={{ marginTop: 4 }}>
                      {o.tech_domains.map(d => <Tag key={d}>{d}</Tag>)}
                    </div>
                  )}
                  {o.owner_orgs.length > 0 && (
                    <div style={{ marginTop: 4 }}>
                      <Text type="secondary">归属机构: </Text>
                      {o.owner_orgs.map(org => <Tag key={org} color="green">{org}</Tag>)}
                    </div>
                  )}
                </Card>
              )),
          },
          {
            key: 'graph', label: '关联图谱',
            children: relations.isLoading ? <Spin /> : relations.isError ? <Alert type="error" message="加载失败" /> : (
              relations.data && relations.data.items.length > 0
                ? <RelationGraph relations={relations.data.items} />
                : <Text type="secondary">暂无关联数据</Text>
            ),
          },
        ]} />
      )}
    </Drawer>
  )
}

export default function ProfileProject() {
  const qc = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['project-search', keyword, page],
    queryFn: () => projectService.search(keyword, page, 20),
  })

  const importMut = useMutation({
    mutationFn: (profiles: Partial<ProjectProfile>[]) => projectService.bulkImport(profiles),
    onSuccess: () => {
      message.success('导入成功')
      qc.invalidateQueries({ queryKey: ['project-search'] })
    },
    onError: () => message.error('导入失败'),
  })

  const cols = [
    { title: 'ID', dataIndex: 'project_id', width: 180, ellipsis: true },
    {
      title: '项目名称',
      dataIndex: 'name_cn',
      ellipsis: true,
      render: (v: string[]) => v?.[0] ?? '-',
    },
    {
      title: '技术领域',
      dataIndex: 'tech_domain',
      render: (d: string[]) => d?.slice(0, 2).map(t => <Tag key={t}>{t}</Tag>),
    },
    {
      title: '相关度',
      dataIndex: 'relevance_score',
      width: 90,
      render: (v: number | null) => v != null ? v.toFixed(3) : '-',
    },
    {
      title: '操作',
      width: 80,
      render: (_: unknown, r: ProjectSearchItem) => (
        <Button type="link" size="small" onClick={() => setSelectedId(r.project_id)}>详情</Button>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Search
          placeholder="搜索项目名称或关键词"
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
              } catch { message.error('JSON 解析失败') }
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
        dataSource={data?.items}
        columns={cols}
        rowKey="project_id"
        size="small"
        pagination={{
          current: page, pageSize: 20, total: data?.total,
          onChange: p => setPage(p), showTotal: t => `共 ${t} 条`,
        }}
        onRow={r => ({ onDoubleClick: () => setSelectedId(r.project_id) })}
      />

      {selectedId && (
        <DetailDrawer id={selectedId} open={!!selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  )
}
