import { useState, useEffect } from 'react'
import {
  Row, Col, Card, Table, Tag, Button, DatePicker, Select, Space,
  Alert, Spin, Drawer, Descriptions, Typography, message, Divider, Modal, Tooltip,
} from 'antd'
import { PlayCircleOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { scanService } from '../../api/scan'
import type { FrontierTechItem, AlertItem } from '../../api/types'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker
const { Text } = Typography
const { Option } = Select

const severityColor = (s: string) =>
  s === 'critical' ? 'red' : s === 'warn' ? 'orange' : 'blue'
const severityLabel = (s: string) =>
  ({ critical: '严重', warn: '警告', info: '信息' } as Record<string, string>)[s] ?? s
const frontierStatusLabel = (s: string) =>
  ({ validated: '已验证', pending: '待验证', rejected: '已排除' } as Record<string, string>)[s] ?? s
const alertTypeLabel = (s: string) =>
  ({ burst: '突现', trl_upgrade: 'TRL升级', org_layout: '机构布局' } as Record<string, string>)[s] ?? s

const statusColor = (s: string) =>
  s === 'validated' ? 'green' : s === 'pending' ? 'blue' : 'default'

function TechDetailDrawer({
  item, open, onClose,
}: { item: FrontierTechItem | null; open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [verifyTaskId, setVerifyTaskId] = useState<string | null>(null)
  const verifyMut = useMutation({
    mutationFn: () => scanService.verify(item!.id),
    onSuccess: (res) => {
      setVerifyTaskId(res.task_id)
      message.loading({ content: 'LLM 验证任务已提交，执行中...', key: 'verify', duration: 2 })
    },
    onError: () => message.error('提交验证失败'),
  })
  const verifyStatus = useQuery({
    queryKey: ['verify-task', verifyTaskId],
    queryFn: () => scanService.getVerifyTaskStatus(verifyTaskId!),
    enabled: !!verifyTaskId,
    refetchInterval: (q) => (q.state.data?.state === 'SUCCESS' || q.state.data?.state === 'FAILURE') ? false : 2000,
  })
  useEffect(() => {
    const st = verifyStatus.data
    if (!st || (st.state !== 'SUCCESS' && st.state !== 'FAILURE')) return
    if (st.state === 'SUCCESS' && st.status === 'done') {
      message.success(`LLM 验证完成：判定=${st.llm_verdict ?? '-'}，状态=${st.frontier_status ?? '-'}`)
    } else {
      message.error('LLM 验证失败：' + (st.error ?? '未知错误'))
    }
    qc.invalidateQueries({ queryKey: ['frontier'] })
    setVerifyTaskId(null)
    onClose()
  }, [verifyStatus.data?.state])

  if (!item) return null
  return (
    <Drawer
      title={item.tech_name}
      width={520}
      open={open}
      onClose={onClose}
      extra={item.status === 'pending' && (
        <Tooltip title="异步调用 LLM agent 做真实性/时效性/突破性 4 步验证，按判定回写状态（是→已验证/否→已排除）。">
          <Button
            size="small"
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={verifyMut.isPending || !!verifyTaskId}
            onClick={() => verifyMut.mutate()}
          >
            {verifyTaskId ? '验证中...' : 'LLM 验证'}
          </Button>
        </Tooltip>
      )}
    >
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="技术名称">{item.tech_name}</Descriptions.Item>
        <Descriptions.Item label="领域">
          {item.tech_domain.map(d => <Tag key={d}>{d}</Tag>)}
        </Descriptions.Item>
        <Descriptions.Item label="状态"><Tag color={statusColor(item.status)}>{frontierStatusLabel(item.status)}</Tag></Descriptions.Item>
        <Descriptions.Item label="TRL">{item.trl_level ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="分析周期">{item.period_from?.slice(0, 10)} ~ {item.period_to?.slice(0, 10)}</Descriptions.Item>
        <Descriptions.Item label="融合评分">{item.fusion_score.toFixed(4)}</Descriptions.Item>
        <Descriptions.Item label="爆发评分">{item.burst_score.toFixed(4)}</Descriptions.Item>
        <Descriptions.Item label="专利评分">{item.patent_score.toFixed(4)}</Descriptions.Item>
        <Descriptions.Item label="引用评分">{item.citation_score.toFixed(4)}</Descriptions.Item>
        <Descriptions.Item label="投资评分">{item.invest_score.toFixed(4)}</Descriptions.Item>
        <Descriptions.Item label="政策评分">{item.policy_score.toFixed(4)}</Descriptions.Item>
        <Descriptions.Item label="LLM验证">{item.llm_validated ? '是' : '否'}</Descriptions.Item>
        {item.llm_verdict && (
          <Descriptions.Item label="LLM判定">
            <Text style={{ whiteSpace: 'pre-wrap' }}>{item.llm_verdict}</Text>
          </Descriptions.Item>
        )}
      </Descriptions>
    </Drawer>
  )
}

export default function ScanMonitor() {
  const qc = useQueryClient()
  const [dateRange, setDateRange] = useState<[string, string]>(['', ''])
  const [domains, setDomains] = useState<string[]>([])
  const [techPage, setTechPage] = useState(1)
  const [alertPage, setAlertPage] = useState(1)
  const [selectedItem, setSelectedItem] = useState<FrontierTechItem | null>(null)
  const [alertSel, setAlertSel] = useState<AlertItem | null>(null)

  const frontierQ = useQuery({
    queryKey: ['frontier', techPage],
    queryFn: () => scanService.listFrontierTech(techPage, 20),
  })
  const alertsQ = useQuery({
    queryKey: ['alerts', alertPage],
    queryFn: () => scanService.listAlerts(alertPage, 20),
  })

  const scanMut = useMutation({
    mutationFn: () => {
      const [from, to] = dateRange
      if (!from || !to) throw new Error('请选择分析时间范围')
      return scanService.triggerScan(from, to, domains.length ? domains : undefined)
    },
    onSuccess: res => {
      message.success(`扫描任务已提交: ${res.task_id}`)
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ['frontier'] })
        qc.invalidateQueries({ queryKey: ['alerts'] })
      }, 2000)
    },
    onError: (e: Error) => message.error(e.message || '扫描失败'),
  })

  const frontierCols = [
    { title: '技术名称', dataIndex: 'tech_name', ellipsis: true },
    { title: '领域', dataIndex: 'tech_domain', render: (d: string[]) => d.slice(0, 1).map(t => <Tag key={t}>{t}</Tag>) },
    { title: '融合评分', dataIndex: 'fusion_score', render: (v: number) => v.toFixed(3),
      sorter: (a: FrontierTechItem, b: FrontierTechItem) => a.fusion_score - b.fusion_score },
    { title: 'TRL', dataIndex: 'trl_level', width: 60, render: (v: number | null) => v ?? '-' },
    { title: '状态', dataIndex: 'status', render: (v: string) => <Tag color={statusColor(v)}>{frontierStatusLabel(v)}</Tag> },
    {
      title: '操作', width: 80,
      render: (_: unknown, r: FrontierTechItem) => (
        <Button type="link" size="small" onClick={() => setSelectedItem(r)}>详情</Button>
      ),
    },
  ]

  const alertCols = [
    { title: '技术', dataIndex: 'tech_name', ellipsis: true },
    { title: '类型', dataIndex: 'alert_type', width: 100,
      render: (v: string) => alertTypeLabel(v) },
    { title: '级别', dataIndex: 'severity', width: 80,
      render: (v: string) => <Tag color={severityColor(v)}>{severityLabel(v)}</Tag> },
    { title: '消息', dataIndex: 'message', ellipsis: true },
    { title: '时间', dataIndex: 'fired_at', width: 140,
      render: (v: string) => v?.slice(0, 16).replace('T', ' ') },
    {
      title: '操作', width: 70,
      render: (_: unknown, r: AlertItem) => (
        <Button type="link" size="small" onClick={() => setAlertSel(r)}>查看</Button>
      ),
    },
  ]

  return (
    <div>
      <Card title="触发扫描" size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <RangePicker
            onChange={v => setDateRange(v ? [
              dayjs(v[0]).format('YYYY-MM-DD'),
              dayjs(v[1]).format('YYYY-MM-DD'),
            ] : ['', ''])}
          />
          <Select
            mode="tags"
            placeholder="技术领域（可多选）"
            style={{ minWidth: 200 }}
            value={domains}
            onChange={setDomains}
          >
            {['人工智能', '量子计算', '生物技术', '新能源', '先进制造', '新材料'].map(d => (
              <Option key={d} value={d}>{d}</Option>
            ))}
          </Select>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={scanMut.isPending}
            onClick={() => scanMut.mutate()}
          >
            开始扫描
          </Button>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card title="前沿技术列表" size="small">
            {frontierQ.isError ? <Alert type="error" message="加载失败" /> : (
              <Table
                loading={frontierQ.isLoading}
                dataSource={frontierQ.data?.items}
                columns={frontierCols}
                rowKey="id"
                size="small"
                pagination={{
                  current: techPage,
                  pageSize: 20,
                  total: frontierQ.data?.total,
                  onChange: p => setTechPage(p),
                  showTotal: t => `共 ${t} 条`,
                }}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="告警列表" size="small">
            {alertsQ.isError ? <Alert type="error" message="加载失败" /> : (
              <Table
                loading={alertsQ.isLoading}
                dataSource={alertsQ.data?.items}
                columns={alertCols}
                rowKey="id"
                size="small"
                pagination={{
                  current: alertPage,
                  pageSize: 20,
                  total: alertsQ.data?.total,
                  onChange: p => setAlertPage(p),
                  showTotal: t => `共 ${t} 条`,
                }}
              />
            )}
          </Card>
        </Col>
      </Row>

      <TechDetailDrawer
        item={selectedItem}
        open={!!selectedItem}
        onClose={() => setSelectedItem(null)}
      />

      <Modal
        title="告警详情"
        open={!!alertSel}
        onOk={() => setAlertSel(null)}
        onCancel={() => setAlertSel(null)}
        cancelButtonProps={{ style: { display: 'none' } }}
      >
        {alertSel && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="技术">{alertSel.tech_name}</Descriptions.Item>
            <Descriptions.Item label="类型">{alertTypeLabel(alertSel.alert_type)}</Descriptions.Item>
            <Descriptions.Item label="级别">
              <Tag color={severityColor(alertSel.severity)}>{severityLabel(alertSel.severity)}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="时间">{alertSel.fired_at?.slice(0, 19).replace('T', ' ')}</Descriptions.Item>
            <Descriptions.Item label="告警消息">
              <Text style={{ whiteSpace: 'pre-wrap' }}>{alertSel.message}</Text>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  )
}
