import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Row, Col, Card, Table, Tag, Button, Space, Alert,
  Drawer, Descriptions, Typography, message, Spin,
} from 'antd'
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { discoveryService } from '../../api/discovery'
import { NAV_TYPES } from '../../utils/crossProfile'
import type { WeakSignalItem, SignalNetwork } from '../../api/types'
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
        labelCfg: { position: 'bottom', style: { fontSize: 10 } },
      },
      defaultEdge: {
        style: { lineWidth: 1, stroke: '#aaa' },
        labelCfg: { style: { fontSize: 9, fill: '#999' } },
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
        <Descriptions.Item label="领域">{signal.domain ?? '-'}</Descriptions.Item>
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

export default function NewTechDiscovery() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<WeakSignalItem | null>(null)

  const signalsQ = useQuery({
    queryKey: ['signals', page],
    queryFn: () => discoveryService.listSignals(page, 20),
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
    { title: '强度', dataIndex: 'strength', width: 80, render: (v: number) => v.toFixed(3) },
    { title: '新颖度', dataIndex: 'novelty', width: 80, render: (v: number) => v.toFixed(3) },
    { title: '一致性', dataIndex: 'coherence', width: 80, render: (v: number) => v.toFixed(3) },
    { title: '领域', dataIndex: 'domain', width: 100, render: (v: string | null) => v ?? '-' },
    { title: '状态', dataIndex: 'status', width: 90,
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
              pageSize: 20,
              total: signalsQ.data?.total,
              onChange: p => setPage(p),
              showTotal: t => `共 ${t} 条`,
            }}
          />
        )}
      </Card>

      <SignalDrawer signal={selected} open={!!selected} onClose={() => setSelected(null)} />
    </div>
  )
}
