import { useState, useRef, useEffect } from 'react'
import {
  Input, Button, Table, Tag, Drawer, Tabs, Spin, Alert,
  Descriptions, Space, Typography, Row, Col, Card, Statistic,
  Modal, Form, Select, Upload, message, Progress, Timeline,
} from 'antd'
import {
  SearchOutlined, PlusOutlined, UploadOutlined, ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { techService } from '../../api/tech'
import type { TechProfile, TechSearchResultItem, RelationItem } from '../../api/types'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell, ResponsiveContainer, Legend,
} from 'recharts'
import G6 from '@antv/g6'

const { Search } = Input
const { Text } = Typography
const { Option } = Select

const DOMAIN_COLORS = ['#1677ff', '#52c41a', '#fa8c16', '#722ed1', '#eb2f96', '#13c2c2']

const ENTITY_NODE_COLOR: Record<string, string> = {
  tech: '#1677ff',
  org: '#52c41a',
  person: '#fa8c16',
  enterprise: '#722ed1',
}

function DomainBar({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).slice(0, 10).map(([k, v]) => ({ name: k, count: v }))
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={entries} margin={{ left: -20 }}>
        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
        <YAxis allowDecimals={false} />
        <Tooltip />
        <Bar dataKey="count" fill="#1677ff" />
      </BarChart>
    </ResponsiveContainer>
  )
}

function CompletenessChart({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).map(([k, v], i) => ({
    name: k, value: v, fill: DOMAIN_COLORS[i % DOMAIN_COLORS.length],
  }))
  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie data={entries} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label>
          {entries.map((e, i) => <Cell key={i} fill={e.fill} />)}
        </Pie>
        <Legend />
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  )
}

function RelationGraph({ relations }: { relations: RelationItem[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const graphRef = useRef<InstanceType<typeof G6.Graph> | null>(null)

  useEffect(() => {
    if (!ref.current) return
    const selfNode = {
      id: '_self',
      label: '当前技术',
      style: { fill: '#ff4d4f', stroke: '#ff4d4f' },
      labelCfg: { style: { fontWeight: 700 } },
    }
    const targetNodes = relations.map(r => ({
      id: r.target_entity_id,
      label: r.target_name ?? r.target_entity_id.slice(0, 8),
      style: {
        fill: ENTITY_NODE_COLOR[r.target_entity_type] ?? '#999',
        stroke: ENTITY_NODE_COLOR[r.target_entity_type] ?? '#999',
      },
    }))
    const edges = relations.map((r, i) => ({
      id: `e${i}`,
      source: '_self',
      target: r.target_entity_id,
      label: r.relation_type,
    }))
    const graph = new G6.Graph({
      container: ref.current,
      width: ref.current.clientWidth || 500,
      height: 340,
      fitView: true,
      layout: { type: 'radial', unitRadius: 130 },
      defaultNode: {
        size: 36,
        labelCfg: { position: 'bottom', style: { fontSize: 11 } },
        style: { fill: '#ccc', stroke: '#ccc' },
      },
      defaultEdge: { labelCfg: { style: { fontSize: 10, fill: '#666' } } },
      modes: { default: ['drag-canvas', 'zoom-canvas', 'drag-node'] },
    })
    graph.data({ nodes: [selfNode, ...targetNodes], edges })
    graph.render()

    graph.on('node:click', (evt: { item?: { getModel?: () => { id?: string; _entityType?: string } } }) => {
      const model = evt.item?.getModel?.()
      if (!model || model.id === '_self') return
    })

    graphRef.current = graph
    return () => { graph.destroy(); graphRef.current = null }
  }, [relations])

  return (
    <div>
      <Space size={8} style={{ marginBottom: 8, flexWrap: 'wrap' }}>
        {Object.entries(ENTITY_NODE_COLOR).map(([type, color]) => (
          <Tag key={type} color={color}>{type}</Tag>
        ))}
      </Space>
      <div ref={ref} style={{ width: '100%', height: 340, background: '#fafafa', borderRadius: 4 }} />
    </div>
  )
}

function DetailDrawer({ id, open, onClose }: { id: string; open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const profile = useQuery({
    queryKey: ['tech', id],
    queryFn: () => techService.getById(id),
    enabled: open && !!id,
  })
  const relations = useQuery({
    queryKey: ['tech-relations', id],
    queryFn: () => techService.getRelations(id),
    enabled: open && !!id,
  })
  const stats = useQuery({
    queryKey: ['stats', 'tech'],
    queryFn: techService.getStats,
  })
  const enrichMut = useMutation({
    mutationFn: () => techService.enrich(id),
    onSuccess: (res) => {
      message.success(`LLM补全任务已提交: ${res.task_id}`)
      qc.invalidateQueries({ queryKey: ['tech', id] })
    },
    onError: () => message.error('提交补全任务失败'),
  })

  const p = profile.data

  const completenessPercent = p?.completeness != null ? Math.round(p.completeness * 100) : null

  const drawerTitle = (
    <Space>
      <span>{p?.tech_name_cn ?? id}</span>
      {completenessPercent != null && (
        <Progress
          percent={completenessPercent}
          size="small"
          style={{ width: 120, marginBottom: 0 }}
          status={completenessPercent >= 80 ? 'success' : completenessPercent >= 50 ? 'normal' : 'exception'}
        />
      )}
      <Button
        size="small"
        icon={<ThunderboltOutlined />}
        loading={enrichMut.isPending}
        onClick={() => enrichMut.mutate()}
      >
        LLM补全
      </Button>
    </Space>
  )

  return (
    <Drawer title={drawerTitle} width={700} open={open} onClose={onClose} destroyOnClose>
      {profile.isLoading ? <Spin /> : profile.isError ? <Alert type="error" message="加载失败" /> : (
        <Tabs items={[
          {
            key: 'info', label: '基本信息',
            children: p && (
              <Descriptions column={1} size="small" bordered>
                <Descriptions.Item label="技术ID">{p.tech_id}</Descriptions.Item>
                <Descriptions.Item label="中文名">{p.tech_name_cn}</Descriptions.Item>
                <Descriptions.Item label="英文名">{p.tech_name_en ?? '-'}</Descriptions.Item>
                {p.tech_name_other && <Descriptions.Item label="其他名称">{p.tech_name_other}</Descriptions.Item>}
                <Descriptions.Item label="领域">
                  {p.tech_domain.map(d => <Tag key={d}>{d}</Tag>)}
                </Descriptions.Item>
                {p.invention_date && <Descriptions.Item label="发明时间">{p.invention_date}</Descriptions.Item>}
                {p.application_date && <Descriptions.Item label="应用时间">{p.application_date}</Descriptions.Item>}
                <Descriptions.Item label="技术简介">
                  <Text style={{ whiteSpace: 'pre-wrap' }}>{p.tech_summary ?? '-'}</Text>
                </Descriptions.Item>
                {p.dev_goal && <Descriptions.Item label="发展目标"><Text style={{ whiteSpace: 'pre-wrap' }}>{p.dev_goal}</Text></Descriptions.Item>}
                <Descriptions.Item label="发展现状">
                  <Text style={{ whiteSpace: 'pre-wrap' }}>{p.current_status ?? '-'}</Text>
                </Descriptions.Item>
                <Descriptions.Item label="发展趋势">
                  <Text style={{ whiteSpace: 'pre-wrap' }}>{p.trend ?? '-'}</Text>
                </Descriptions.Item>
                {p.tech_advantages && <Descriptions.Item label="技术优势"><Text style={{ whiteSpace: 'pre-wrap' }}>{p.tech_advantages}</Text></Descriptions.Item>}
                {p.autonomy_capability && <Descriptions.Item label="自主可控能力">{p.autonomy_capability}</Descriptions.Item>}
                {p.key_points.length > 0 && (
                  <Descriptions.Item label="关键技术点">
                    {p.key_points.map((k, i) => <Tag key={i}>{k}</Tag>)}
                  </Descriptions.Item>
                )}
                <Descriptions.Item label="置信度">{(p.confidence * 100).toFixed(1)}%</Descriptions.Item>
                <Descriptions.Item label="完整度">
                  {completenessPercent != null
                    ? <Progress percent={completenessPercent} size="small" style={{ width: 180 }} />
                    : '-'}
                </Descriptions.Item>
              </Descriptions>
            ),
          },
          {
            key: 'milestones', label: `里程碑 (${p?.dev_milestones?.length ?? 0})`,
            children: p && (
              p.dev_milestones.length === 0
                ? <Text type="secondary">暂无里程碑数据</Text>
                : (
                  <Timeline
                    mode="left"
                    items={p.dev_milestones.map((m, i) => ({
                      key: i,
                      label: m.milestone_date ?? '未知日期',
                      children: (
                        <div>
                          <Text strong>{m.milestone_name ?? '未命名事件'}</Text>
                          {m.milestone_content && (
                            <div style={{ marginTop: 4, color: '#595959' }}>{m.milestone_content}</div>
                          )}
                          {m.contributor_keywords.length > 0 && (
                            <div style={{ marginTop: 4 }}>
                              {m.contributor_keywords.map((k, j) => <Tag key={j} color="blue">{k}</Tag>)}
                            </div>
                          )}
                        </div>
                      ),
                    }))}
                  />
                )
            ),
          },
          {
            key: 'research', label: '科研成果',
            children: p && (
              <Space direction="vertical" style={{ width: '100%' }} size={16}>
                <Card title={`经费投入 (${p.funding.length})`} size="small">
                  {p.funding.length === 0
                    ? <Text type="secondary">暂无数据</Text>
                    : (
                      <Table
                        size="small"
                        dataSource={p.funding}
                        rowKey={(_, i) => String(i)}
                        pagination={false}
                        columns={[
                          { title: '来源', dataIndex: 'source', render: v => v ?? '-' },
                          { title: '金额（万元）', dataIndex: 'amount', render: v => v != null ? v.toLocaleString() : '-', width: 120 },
                        ]}
                      />
                    )}
                </Card>
                <Card title={`学术成果 (${p.academic_outputs.length})`} size="small">
                  {p.academic_outputs.length === 0
                    ? <Text type="secondary">暂无数据</Text>
                    : (
                      <Table
                        size="small"
                        dataSource={p.academic_outputs}
                        rowKey={(_, i) => String(i)}
                        pagination={false}
                        columns={[
                          { title: '成果名称', dataIndex: 'name', render: v => v ?? '-', ellipsis: true },
                          { title: '发布时间', dataIndex: 'publish_date', width: 110, render: v => v ?? '-' },
                          {
                            title: '主体关键词', dataIndex: 'subject_keywords',
                            render: (v: string[]) => v.map((k, i) => <Tag key={i}>{k}</Tag>),
                          },
                        ]}
                      />
                    )}
                </Card>
                <Card title={`科研实验 (${p.experiments.length})`} size="small">
                  {p.experiments.length === 0
                    ? <Text type="secondary">暂无数据</Text>
                    : (
                      <Table
                        size="small"
                        dataSource={p.experiments}
                        rowKey={(_, i) => String(i)}
                        pagination={false}
                        columns={[
                          { title: '实验日期', dataIndex: 'experiment_date', width: 110, render: v => v ?? '-' },
                          { title: '实验内容', dataIndex: 'content', ellipsis: true, render: v => v ?? '-' },
                          { title: '实验结果', dataIndex: 'result', ellipsis: true, render: v => v ?? '-' },
                        ]}
                      />
                    )}
                </Card>
              </Space>
            ),
          },
          {
            key: 'stats', label: '统计图表',
            children: stats.isLoading ? <Spin /> : stats.data ? (
              <Space direction="vertical" style={{ width: '100%' }} size={16}>
                <Row gutter={16}>
                  <Col span={8}><Statistic title="总数" value={stats.data.total} /></Col>
                  <Col span={8}><Statistic title="本期新增" value={stats.data.new_this_period} /></Col>
                  <Col span={8}><Statistic title="本期更新" value={stats.data.updated_this_period} /></Col>
                </Row>
                <Card title="领域分布" size="small">
                  <DomainBar data={stats.data.domain_distribution} />
                </Card>
                <Card title="完整度分布" size="small">
                  <CompletenessChart data={stats.data.completeness_histogram} />
                </Card>
              </Space>
            ) : null,
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

export default function ProfileTech() {
  const qc = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [form] = Form.useForm()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['tech-search', keyword, page],
    queryFn: () => techService.search(keyword, page, 20),
  })

  const importMut = useMutation({
    mutationFn: (profiles: Partial<TechProfile>[]) => techService.bulkImport(profiles),
    onSuccess: (res) => {
      message.success(`导入成功: ${res.accepted_count} 条`)
      qc.invalidateQueries({ queryKey: ['tech-search'] })
      qc.invalidateQueries({ queryKey: ['stats', 'tech'] })
    },
    onError: () => message.error('导入失败'),
  })

  const createMut = useMutation({
    mutationFn: (values: Record<string, unknown>) => techService.bulkImport([{
      tech_name_cn: values.tech_name_cn as string,
      tech_name_en: values.tech_name_en as string,
      tech_domain: (values.tech_domain as string[]) ?? [],
      tech_summary: values.tech_summary as string,
      current_status: values.current_status as string,
    }]),
    onSuccess: () => {
      message.success('创建成功')
      setCreateOpen(false)
      form.resetFields()
      qc.invalidateQueries({ queryKey: ['tech-search'] })
    },
    onError: () => message.error('创建失败'),
  })

  const cols = [
    { title: 'ID', dataIndex: 'tech_id', width: 180, ellipsis: true },
    { title: '名称', dataIndex: 'tech_name_cn', ellipsis: true },
    {
      title: '领域',
      dataIndex: 'tech_domain',
      render: (d: string[]) => d.slice(0, 2).map(t => <Tag key={t}>{t}</Tag>),
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
      render: (_: unknown, r: TechSearchResultItem) => (
        <Button type="link" size="small" onClick={() => setSelectedId(r.tech_id)}>详情</Button>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Search
          placeholder="搜索技术名称或关键词"
          allowClear
          style={{ width: 300 }}
          onSearch={v => { setKeyword(v); setPage(1) }}
          enterButton={<SearchOutlined />}
        />
        <Button icon={<PlusOutlined />} type="primary" onClick={() => setCreateOpen(true)}>新建</Button>
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
        dataSource={data?.items}
        columns={cols}
        rowKey="tech_id"
        size="small"
        pagination={{
          current: page,
          pageSize: 20,
          total: data?.total,
          onChange: p => setPage(p),
          showTotal: t => `共 ${t} 条`,
        }}
        onRow={r => ({ onDoubleClick: () => setSelectedId(r.tech_id) })}
      />

      {selectedId && (
        <DetailDrawer
          id={selectedId}
          open={!!selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}

      <Modal
        title="新建技术画像"
        open={createOpen}
        onCancel={() => { setCreateOpen(false); form.resetFields() }}
        onOk={() => form.validateFields().then(v => createMut.mutate(v))}
        confirmLoading={createMut.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="tech_name_cn" label="中文名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="tech_name_en" label="英文名">
            <Input />
          </Form.Item>
          <Form.Item name="tech_domain" label="领域">
            <Select mode="tags" placeholder="输入领域后回车" />
          </Form.Item>
          <Form.Item name="current_status" label="状态">
            <Select allowClear>
              <Option value="emerging">emerging</Option>
              <Option value="growing">growing</Option>
              <Option value="mature">mature</Option>
              <Option value="declining">declining</Option>
            </Select>
          </Form.Item>
          <Form.Item name="tech_summary" label="摘要">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
