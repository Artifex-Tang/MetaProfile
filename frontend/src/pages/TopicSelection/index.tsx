import { useState } from 'react'
import {
  Table, Tag, Button, Space, Alert, Card, Drawer, Descriptions,
  Typography, message, Modal, Form, InputNumber, DatePicker,
  Rate, Input, Select, Row, Col, Statistic,
} from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { topicService } from '../../api/topic'
import { NAV_TYPES } from '../../utils/crossProfile'
import type { TopicItem, TopicDetail } from '../../api/types'
import dayjs from 'dayjs'

const { Text, Paragraph } = Typography
const { Option } = Select
const { RangePicker } = DatePicker

const statusColor = (s: string) => {
  const m: Record<string, string> = {
    pending: 'default', accepted: 'green', rejected: 'red', revised: 'orange',
  }
  return m[s] ?? 'default'
}

const statusLabel = (s: string) => {
  const m: Record<string, string> = {
    pending: '待处理', accepted: '已采纳', rejected: '已拒绝', revised: '已修订',
  }
  return m[s] ?? s
}

function scoreBar(label: string, value: number) {
  const pct = Math.round(value * 100)
  return (
    <div style={{ marginBottom: 4 }}>
      <Text type="secondary" style={{ fontSize: 12, display: 'inline-block', width: 90 }}>{label}</Text>
      <div style={{ display: 'inline-block', background: '#f0f0f0', borderRadius: 4, width: 140, height: 12, verticalAlign: 'middle' }}>
        <div style={{ background: '#1677ff', borderRadius: 4, width: `${pct}%`, height: '100%' }} />
      </div>
      <Text style={{ marginLeft: 8, fontSize: 12 }}>{value.toFixed(3)}</Text>
    </div>
  )
}

/** 关联实体 Tag：点击跳转对应画像详情（tech/org/project 可跳）。 */
function JumpTag({ type, id, label, color }: { type: string; id: string; label: string; color: string }) {
  const navigate = useNavigate()
  if (!NAV_TYPES.has(type.toLowerCase())) return <Tag color={color}>{label}</Tag>
  return (
    <Tag
      color={color}
      style={{ cursor: 'pointer' }}
      onClick={() => navigate(`/${type.toLowerCase()}/${encodeURIComponent(id)}`)}
    >
      {label}
    </Tag>
  )
}

function TopicDrawer({
  id, open, onClose,
}: { id: string; open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [fbOpen, setFbOpen] = useState(false)
  const [fbForm] = Form.useForm()

  const detail = useQuery({
    queryKey: ['topic', id],
    queryFn: () => topicService.getById(id),
    enabled: open && !!id,
  })

  const feedbackMut = useMutation({
    mutationFn: (v: { rating: 'accept' | 'reject' | 'revise'; score: number; comments?: string }) =>
      topicService.feedback(id, v.rating, v.score, v.comments),
    onSuccess: () => {
      message.success('反馈已提交')
      setFbOpen(false)
      fbForm.resetFields()
      qc.invalidateQueries({ queryKey: ['topics'] })
      qc.invalidateQueries({ queryKey: ['topic', id] })
    },
    onError: () => message.error('提交失败'),
  })

  const d = detail.data as TopicDetail | undefined

  return (
    <Drawer
      title={d?.title ?? id}
      width={620}
      open={open}
      onClose={onClose}
      destroyOnClose
      extra={
        <Button type="primary" onClick={() => setFbOpen(true)}>提交反馈</Button>
      }
    >
      {detail.isLoading ? null : detail.isError ? <Alert type="error" message="加载失败" /> : d && (
        <Space direction="vertical" style={{ width: '100%' }} size={16}>
          <Card size="small" title="基本信息">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="选题ID">{d.topic_id}</Descriptions.Item>
              <Descriptions.Item label="周期">{d.period ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="状态"><Tag color={statusColor(d.status)}>{d.status}</Tag></Descriptions.Item>
            </Descriptions>
            <Paragraph style={{ marginTop: 8 }}>{d.summary}</Paragraph>
          </Card>

          <Card size="small" title="评分详情">
            {scoreBar('热度', d.score_hot)}
            {scoreBar('政策', d.score_policy)}
            {scoreBar('影响力', d.score_impact)}
            {scoreBar('去重', d.score_dedup)}
            {scoreBar('LLM', d.score_llm_gen)}
            <div style={{ marginTop: 8, borderTop: '1px solid #f0f0f0', paddingTop: 8 }}>
              <Row gutter={16}>
                <Col span={6}><Statistic title="新颖度" value={d.review_novelty.toFixed(2)} /></Col>
                <Col span={6}><Statistic title="重要性" value={d.review_importance.toFixed(2)} /></Col>
                <Col span={6}><Statistic title="可行性" value={d.review_feasibility.toFixed(2)} /></Col>
                <Col span={6}><Statistic title="表达" value={d.review_expression.toFixed(2)} /></Col>
              </Row>
              <Statistic title="综合评分" value={d.final_score.toFixed(3)} style={{ marginTop: 8 }} />
            </div>
          </Card>

          {d.review_evidence && (
            <Card size="small" title="评审依据">
              <Text style={{ whiteSpace: 'pre-wrap' }}>{d.review_evidence}</Text>
            </Card>
          )}

          {d.related_tech_ids.length > 0 && (
            <Card size="small" title="关联技术">
              {d.related_tech_ids.map((id, i) => (
                <JumpTag key={`tech-${id}-${i}`} type="tech" id={id} label={d.related_tech_names?.[i] ?? id} color="blue" />
              ))}
            </Card>
          )}
          {d.related_org_ids?.length > 0 && (
            <Card size="small" title="关联机构">
              {d.related_org_ids.map((id, i) => (
                <JumpTag key={`org-${id}-${i}`} type="org" id={id} label={d.related_org_names?.[i] ?? id} color="green" />
              ))}
            </Card>
          )}
          {d.related_project_ids?.length > 0 && (
            <Card size="small" title="关联项目">
              {d.related_project_ids.map((id, i) => (
                <JumpTag key={`proj-${id}-${i}`} type="project" id={id} label={d.related_project_names?.[i] ?? id} color="purple" />
              ))}
            </Card>
          )}
        </Space>
      )}

      <Modal
        title="提交反馈"
        open={fbOpen}
        onCancel={() => { setFbOpen(false); fbForm.resetFields() }}
        onOk={() => fbForm.validateFields().then(v => feedbackMut.mutate(v))}
        confirmLoading={feedbackMut.isPending}
      >
        <Form form={fbForm} layout="vertical">
          <Form.Item name="rating" label="评审结论" rules={[{ required: true }]}>
            <Select>
              <Option value="accept">接受</Option>
              <Option value="reject">拒绝</Option>
              <Option value="revise">修改</Option>
            </Select>
          </Form.Item>
          <Form.Item name="score" label="评分 (1-10)" rules={[{ required: true }]} initialValue={7}>
            <InputNumber min={1} max={10} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="comments" label="评审意见">
            <Input.TextArea rows={4} placeholder="请输入评审意见（可选）" />
          </Form.Item>
        </Form>
      </Modal>
    </Drawer>
  )
}

export default function TopicSelection() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<string | undefined>()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [genOpen, setGenOpen] = useState(false)
  const [genForm] = Form.useForm()

  const topicsQ = useQuery({
    queryKey: ['topics', page, status],
    queryFn: () => topicService.list(page, 20, status),
  })

  const genMut = useMutation({
    mutationFn: (v: { target_count: number; period?: [dayjs.Dayjs, dayjs.Dayjs] }) =>
      topicService.generate(
        v.target_count,
        v.period?.[0]?.format('YYYY-MM-DD'),
        v.period?.[1]?.format('YYYY-MM-DD'),
      ),
    onSuccess: () => {
      message.success('选题生成任务已提交')
      setGenOpen(false)
      genForm.resetFields()
      setTimeout(() => qc.invalidateQueries({ queryKey: ['topics'] }), 3000)
    },
    onError: () => message.error('生成失败'),
  })

  const cols = [
    { title: '标题', dataIndex: 'title', ellipsis: true,
      render: (v: string, r: TopicItem) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => setSelectedId(r.topic_id)}>{v}</Button>
      ),
    },
    { title: '周期', dataIndex: 'period', width: 100, render: (v: string | null) => v ?? '-' },
    {
      title: '综合评分', dataIndex: 'final_score', width: 100,
      render: (v: number) => v.toFixed(3),
      sorter: (a: TopicItem, b: TopicItem) => a.final_score - b.final_score,
    },
    {
      title: '状态', dataIndex: 'status', width: 80,
      render: (v: string) => <Tag color={statusColor(v)}>{statusLabel(v)}</Tag>,
    },
    {
      title: '热度', dataIndex: 'score_hot', width: 80,
      render: (v: number) => v.toFixed(2),
    },
    {
      title: '操作', width: 80,
      render: (_: unknown, r: TopicItem) => (
        <Button type="link" size="small" onClick={() => setSelectedId(r.topic_id)}>详情</Button>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          allowClear
          placeholder="状态筛选"
          style={{ width: 140 }}
          value={status}
          onChange={v => { setStatus(v); setPage(1) }}
        >
          <Option value="pending">待处理</Option>
          <Option value="accepted">已采纳</Option>
          <Option value="rejected">已拒绝</Option>
          <Option value="revised">已修订</Option>
        </Select>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setGenOpen(true)}
        >
          生成选题
        </Button>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => qc.invalidateQueries({ queryKey: ['topics'] })}
        >
          刷新
        </Button>
      </Space>

      <Card title="选题候选列表" size="small">
        {topicsQ.isError ? <Alert type="error" message="加载失败" /> : (
          <Table
            loading={topicsQ.isLoading}
            dataSource={topicsQ.data?.items}
            columns={cols}
            rowKey="id"
            size="small"
            pagination={{
              current: page,
              pageSize: 20,
              total: topicsQ.data?.total,
              onChange: p => setPage(p),
              showTotal: t => `共 ${t} 条`,
            }}
          />
        )}
      </Card>

      {selectedId && (
        <TopicDrawer id={selectedId} open={!!selectedId} onClose={() => setSelectedId(null)} />
      )}

      <Modal
        title="生成选题"
        open={genOpen}
        onCancel={() => { setGenOpen(false); genForm.resetFields() }}
        onOk={() => genForm.validateFields().then(v => genMut.mutate(v))}
        confirmLoading={genMut.isPending}
      >
        <Form form={genForm} layout="vertical">
          <Form.Item name="target_count" label="生成数量" rules={[{ required: true }]} initialValue={10}>
            <InputNumber min={1} max={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="period" label="分析周期（可选）">
            <RangePicker style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
