import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Row, Col, Card, Table, Tag, Button, Space, Alert, Tabs, Tooltip,
  Drawer, Descriptions, Typography, message, Spin,
} from 'antd'
import { PlayCircleOutlined, ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { discoveryService } from '../../api/discovery'
import { NAV_TYPES } from '../../utils/crossProfile'
import { G6_FONT_FAMILY } from '../../utils/relationMeta'
import type { DisruptionItem, EmergenceItem, WeakSignalItem, SignalNetwork } from '../../api/types'
import G6 from '@antv/g6'

const { Text } = Typography

const NODE_TYPE_COLOR: Record<string, string> = {
  tech: '#1677ff',
  org: '#52c41a',
  person: '#fa8c16',
  signal: '#722ed1',
}

function SignalGraph({
  network, onNodeClick,
}: { network: SignalNetwork; onNodeClick?: (node: { id: string; entityType: string }) => void }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || !network) return
    const graph = new G6.Graph({
      container: ref.current,
      width: ref.current.clientWidth || 520,
      height: 380,
      fitView: true,
      layout: { type: 'force', preventOverlap: true, linkDistance: 90, nodeStrength: -30 },
      defaultNode: {
        size: 32,
        labelCfg: { position: 'bottom', style: { fontSize: 10, fontFamily: G6_FONT_FAMILY } },
      },
      defaultEdge: {
        style: { lineWidth: 1, stroke: '#aaa' },
        labelCfg: { style: { fontSize: 9, fill: '#999', fontFamily: G6_FONT_FAMILY } },
      },
      modes: { default: ['drag-canvas', 'zoom-canvas', 'drag-node'] },
    })

    const nodes = network.nodes.map(n => ({
      id: n.entity_id,
      label: (n.name ?? n.entity_id).slice(0, 12),
      entityType: n.entity_type,
      style: { fill: NODE_TYPE_COLOR[n.entity_type] ?? '#888' },
    }))
    const edges = network.edges.map((e, i) => ({
      id: `e${i}`,
      source: e.source_id,
      target: e.target_id,
      label: e.edge_type,
      style: { lineWidth: Math.max(1, e.weight * 3) },
    }))

    graph.data({ nodes, edges })
    graph.render()

    if (onNodeClick) {
      graph.on('node:click', (e: { item?: { getModel: () => { id?: string; entityType?: string } } }) => {
        const model = e.item?.getModel()
        if (model?.id && model?.entityType) onNodeClick({ id: model.id, entityType: model.entityType })
      })
    }

    return () => graph.destroy()
  }, [network, onNodeClick])

  return <div ref={ref} style={{ width: '100%', height: 380, background: '#fafafa', borderRadius: 4 }} />
}

function SignalDrawer({
  signal, open, onClose,
}: { signal: WeakSignalItem | null; open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const netQ = useQuery({
    queryKey: ['signal-network', signal?.signal_id],
    queryFn: () => discoveryService.getNetwork(signal!.signal_id),
    enabled: open && !!signal,
  })

  const handleNodeClick = ({ id, entityType }: { id: string; entityType: string }) => {
    const t = entityType.toLowerCase()
    if (!NAV_TYPES.has(t)) return
    navigate(`/${t}/${encodeURIComponent(id)}`)
  }

  if (!signal) return null
  return (
    <Drawer title={`信号 ${signal.signal_id.slice(0, 12)}…`} width={600} open={open} onClose={onClose} destroyOnClose>
      <Descriptions column={1} size="small" bordered style={{ marginBottom: 16 }}>
        <Descriptions.Item label="关键词">
          {signal.keywords.map(k => <Tag key={k}>{k}</Tag>)}
        </Descriptions.Item>
        <Descriptions.Item label="强度">{signal.strength.toFixed(3)}</Descriptions.Item>
        <Descriptions.Item label="新颖度">{signal.novelty.toFixed(3)}</Descriptions.Item>
        <Descriptions.Item label="一致性">{signal.coherence.toFixed(3)}</Descriptions.Item>
        <Descriptions.Item label="多样性">{signal.diversity.toFixed(3)}</Descriptions.Item>
        <Descriptions.Item label="增速">{signal.velocity.toFixed(3)}</Descriptions.Item>
        <Descriptions.Item label="领域">{signal.domain ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="证据文档">
          {signal.evidence_doc_ids?.length
            ? <Space size={4} wrap>{signal.evidence_doc_ids.slice(0, 10).map(d =>
                <Tag key={d} color="geekblue">{d}</Tag>)}
              {signal.evidence_doc_ids.length > 10
                ? <Text type="secondary">+{signal.evidence_doc_ids.length - 10}</Text> : null}
            </Space>
            : <Text type="secondary">-</Text>}
        </Descriptions.Item>
        <Descriptions.Item label="状态"><Tag>{signal.status}</Tag></Descriptions.Item>
        <Descriptions.Item label="周期">
          {signal.period_from?.slice(0, 10)} ~ {signal.period_to?.slice(0, 10)}
        </Descriptions.Item>
      </Descriptions>

      <Text strong>信号关联网络</Text>
      {netQ.isLoading ? <Spin style={{ display: 'block', margin: '24px auto' }} /> :
       netQ.isError ? <Alert type="error" message="网络加载失败" /> :
       netQ.data && netQ.data.nodes.length > 0
         ? <SignalGraph network={netQ.data} onNodeClick={handleNodeClick} />
         : <Text type="secondary">暂无关联节点</Text>}
    </Drawer>
  )
}

const QUADRANT_COLOR: Record<string, string> = {
  weak: 'purple', strong: 'red', latent: 'default', nswb: 'blue',
}
const QUADRANT_LABEL: Record<string, string> = {
  weak: '弱信号', strong: '强势', latent: '潜伏', nswb: '成熟',
}
const VERDICT_COLOR: Record<string, string> = {
  '是': 'red', '待定': 'orange', '否': 'default', pending: 'default',
}
const STAGE_LABEL: Record<string, string> = {
  emerging: '新兴', growth: '成长', mature: '成熟', saturated: '饱和', insufficient: '-',
}

function EmergenceTable() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [quadrant, setQuadrant] = useState<string | undefined>()
  const q = useQuery({
    queryKey: ['emergence', page, pageSize, quadrant],
    queryFn: () => discoveryService.listEmergence({
      object_type: 'ipc_domain', quadrant, page, page_size: pageSize,
    }),
  })
  const mut = useMutation({
    mutationFn: () => discoveryService.computeEmergence(),
    onSuccess: res => {
      message.success(res.detail)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['emergence'] }), 3000)
    },
    onError: () => message.error('新兴指标计算失败'),
  })
  const cols = [
    { title: '技术域', dataIndex: 'object_id', width: 100 },
    {
      title: 'TEM 象限', dataIndex: ['metrics', 'tem_quadrant'], width: 90,
      render: (v: string) => <Tag color={QUADRANT_COLOR[v] ?? 'default'}>{QUADRANT_LABEL[v] ?? v}</Tag>,
    },
    {
      title: 'S 曲线', dataIndex: ['metrics', 's_curve_stage'], width: 80,
      render: (v: string) => STAGE_LABEL[v] ?? v,
    },
    { title: '专利数', dataIndex: ['metrics', 'patents'], width: 80,
      render: (v: number) => v?.toLocaleString?.() ?? '-' },
    { title: '申请人', dataIndex: ['metrics', 'applicants'], width: 80,
      render: (v: number) => v?.toLocaleString?.() ?? '-' },
    { title: '新进入者比', dataIndex: ['metrics', 'new_entrant_ratio'], width: 95,
      render: (v: number) => v != null ? v.toFixed(3) : '-' },
    { title: '倍增时间', dataIndex: ['metrics', 'doubling_time'], width: 90,
      render: (v: number | null) => v != null ? `${v.toFixed(1)} 年` : '-' },
    { title: 'Haupt 比', dataIndex: ['metrics', 'haupt_ratio'], width: 85,
      render: (v: number | null) => v != null ? v.toFixed(2) : '-' },
    { title: '窗口', dataIndex: 'window_month', width: 90,
      render: (v: string) => v?.slice(0, 4) },
  ]
  return (
    <Card title="新兴指标(IPC 域)" size="small" extra={
      <Space>
        <Tabs size="small" activeKey={quadrant ?? 'all'} onChange={k => { setQuadrant(k === 'all' ? undefined : k); setPage(1) }}
          items={[['all', '全部'], ['weak', '弱信号'], ['strong', '强势'], ['latent', '潜伏'], ['nswb', '成熟']].map(
            ([k, label]) => ({ key: k as string, label: label as string }),
          )}
        />
        <Button icon={<ThunderboltOutlined />} loading={mut.isPending} onClick={() => mut.mutate()}>
          重算指标
        </Button>
      </Space>
    }>
      {q.isError ? <Alert type="error" message="加载失败" /> : (
        <Table
          loading={q.isLoading}
          dataSource={q.data?.items}
          columns={cols}
          rowKey={r => `${r.object_type}:${r.object_id}:${r.window_month}`}
          size="small"
          pagination={{
            current: page, pageSize, total: q.data?.total,
            showSizeChanger: true, pageSizeOptions: [10, 20, 50],
            onChange: (p, ps) => { setPage(p); setPageSize(ps) },
            showTotal: t => `共 ${t} 条`,
          }}
        />
      )}
    </Card>
  )
}

function DisruptionTable() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const q = useQuery({
    queryKey: ['disruption', page, pageSize],
    queryFn: () => discoveryService.listDisruption({ page, page_size: pageSize }),
  })
  const mut = useMutation({
    mutationFn: () => discoveryService.computeDisruption(),
    onSuccess: res => {
      message.success(res.detail)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['disruption'] }), 5000)
    },
    onError: () => message.error('颠覆评估失败'),
  })
  const cols = [
    { title: '技术域', dataIndex: 'object_id', width: 100 },
    { title: 'DisruptScore', dataIndex: 'disrupt_score', width: 110,
      render: (v: number, r: DisruptionItem) => (
        <Tooltip title={r.llm_evidence ?? 'LLM 未评估'}>
          <b style={{ color: v >= 2 ? '#cf1322' : undefined }}>{v.toFixed(3)}</b>
        </Tooltip>
      ),
      sorter: (a: DisruptionItem, b: DisruptionItem) => a.disrupt_score - b.disrupt_score },
    { title: '新颖z', dataIndex: 'novelty_comb', width: 80, render: (v: number) => v.toFixed(2) },
    { title: '增速z', dataIndex: 'growth', width: 80, render: (v: number) => v.toFixed(2) },
    { title: '新进入z', dataIndex: 'new_entrant', width: 85, render: (v: number) => v.toFixed(2) },
    { title: '小团队z', dataIndex: 'small_team', width: 85, render: (v: number) => v.toFixed(2) },
    { title: '新词z', dataIndex: 'term_novelty', width: 80, render: (v: number) => v.toFixed(2) },
    { title: 'LLM 判定', dataIndex: 'llm_verdict', width: 90,
      render: (v: string, r: DisruptionItem) => (
        <Tooltip title={r.llm_scores ? JSON.stringify(r.llm_scores) : ''}>
          <Tag color={VERDICT_COLOR[v] ?? 'default'}>{v === 'pending' ? '待评估' : v}</Tag>
        </Tooltip>
      ) },
    { title: '窗口', dataIndex: 'window_month', width: 90,
      render: (v: string) => v?.slice(0, 4) },
  ]
  return (
    <Card title="颠覆性评估" size="small" extra={
      <Button icon={<ThunderboltOutlined />} loading={mut.isPending} onClick={() => mut.mutate()}>
        重算评估(含 LLM 漏斗)
      </Button>
    }>
      {q.isError ? <Alert type="error" message="加载失败" /> : (
        <Table
          loading={q.isLoading}
          dataSource={q.data?.items}
          columns={cols}
          rowKey={r => `${r.object_type}:${r.object_id}:${r.window_month}`}
          size="small"
          pagination={{
            current: page, pageSize, total: q.data?.total,
            showSizeChanger: true, pageSizeOptions: [10, 20, 50],
            onChange: (p, ps) => { setPage(p); setPageSize(ps) },
            showTotal: t => `共 ${t} 条`,
          }}
        />
      )}
    </Card>
  )
}

export default function NewTechDiscovery() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [selected, setSelected] = useState<WeakSignalItem | null>(null)

  const signalsQ = useQuery({
    queryKey: ['signals', page, pageSize],
    queryFn: () => discoveryService.listSignals(page, pageSize),
  })

  const scanMut = useMutation({
    mutationFn: () => discoveryService.triggerScan(),
    onSuccess: res => {
      message.success(`发现扫描任务: ${res.task_id}`)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['signals'] }), 2000)
    },
    onError: () => message.error('扫描失败'),
  })

  const cols = [
    { title: '关键词', dataIndex: 'keywords',
      render: (ks: string[]) => ks.slice(0, 3).map(k => <Tag key={k}>{k}</Tag>) },
    { title: '强度', dataIndex: 'strength', width: 70, render: (v: number) => v.toFixed(3) },
    { title: '新颖度', dataIndex: 'novelty', width: 70, render: (v: number) => v.toFixed(3) },
    { title: '一致性', dataIndex: 'coherence', width: 70, render: (v: number) => v.toFixed(3) },
    { title: '多样性', dataIndex: 'diversity', width: 70, render: (v: number) => v.toFixed(3) },
    { title: '增速', dataIndex: 'velocity', width: 70, render: (v: number) => v.toFixed(3) },
    {
      title: '关联', width: 140,
      render: (_: unknown, r: WeakSignalItem) => (
        <Space size={2} style={{ cursor: 'pointer' }} onClick={() => setSelected(r)}>
          <Tag color="blue">技术 {r.related_tech_ids.length}</Tag>
          <Tag color="green">机构 {r.related_org_ids.length}</Tag>
          <Tag color="orange">人员 {r.related_person_ids.length}</Tag>
        </Space>
      ),
    },
    { title: '领域', dataIndex: 'domain', width: 100, render: (v: string | null) => v ?? '-' },
    {
      title: '周期', width: 150,
      render: (_: unknown, r: WeakSignalItem) => `${r.period_from?.slice(5) ?? '-'}~${r.period_to?.slice(5) ?? '-'}`,
    },
    { title: '状态', dataIndex: 'status', width: 80,
      render: (v: string) => <Tag color={v === 'active' ? 'green' : 'default'}>{v === 'active' ? '活跃' : v}</Tag> },
    {
      title: '操作', width: 90,
      render: (_: unknown, r: WeakSignalItem) => (
        <Button type="link" size="small" onClick={() => setSelected(r)}>网络图</Button>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          loading={scanMut.isPending}
          onClick={() => scanMut.mutate()}
        >
          触发发现扫描
        </Button>
        <Button icon={<ReloadOutlined />} onClick={() => qc.invalidateQueries({ queryKey: ['signals'] })}>
          刷新
        </Button>
      </Space>

      <Tabs
        defaultActiveKey="signals"
        items={[
          {
            key: 'signals',
            label: '弱信号',
            children: (
              <Card title="弱信号列表" size="small">
                {signalsQ.isError ? <Alert type="error" message="加载失败" /> : (
                  <Table
                    loading={signalsQ.isLoading}
                    dataSource={signalsQ.data?.items}
                    columns={cols}
                    rowKey="id"
                    size="small"
                    pagination={{
                      current: page,
                      pageSize,
                      total: signalsQ.data?.total,
                      showSizeChanger: true, pageSizeOptions: [10, 20, 50, 100],
                      onChange: (p, ps) => { setPage(p); setPageSize(ps) },
                      showTotal: t => `共 ${t} 条`,
                    }}
                  />
                )}
              </Card>
            ),
          },
          { key: 'emergence', label: '新兴指标', children: <EmergenceTable /> },
          { key: 'disruption', label: '颠覆性', children: <DisruptionTable /> },
        ]}
      />

      <SignalDrawer signal={selected} open={!!selected} onClose={() => setSelected(null)} />
    </div>
  )
}
