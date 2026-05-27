import { useState } from 'react'
import {
  Tabs, Table, Button, Tag, Space, Modal, Form, Input, Select,
  InputNumber, Switch, message, Tooltip, Alert, Drawer,
  Typography, Badge, Descriptions, Popconfirm,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, EditOutlined, SyncOutlined,
  PlayCircleOutlined, CheckCircleOutlined, CloseCircleOutlined,
  ApiOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  settingsService,
  type LLMProviderConfig,
  type DataSourceConfig,
  type CollectionTask,
} from '../../api/settings'

const { Option } = Select
const { Text, Paragraph } = Typography
const { TextArea } = Input

const PROVIDERS = ['openai', 'dashscope', 'deepseek', 'anthropic', 'ollama', 'custom']
const ROLES = ['general', 'extraction', 'generation', 'embedding']
const SOURCE_TYPES = ['rest_api', 'rss', 'nsfc', 'patent_cnipa', 'web_page']
const PROFILE_TYPES = ['tech', 'project', 'org', 'person']

const statusBadge = (s: string) => {
  const map: Record<string, 'success' | 'processing' | 'error' | 'default'> = {
    completed: 'success', running: 'processing', failed: 'error', pending: 'default',
  }
  return <Badge status={map[s] ?? 'default'} text={s} />
}

// ── LLM 配置 Tab ──────────────────────────────────────────────────────────────

function LLMTab() {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<LLMProviderConfig | null>(null)
  const [testResult, setTestResult] = useState<Record<number, { ok: boolean; msg: string }>>({})
  const [form] = Form.useForm()

  const { data = [], isLoading } = useQuery({
    queryKey: ['llm-configs'],
    queryFn: settingsService.listLLM,
  })

  const createMut = useMutation({
    mutationFn: (v: Parameters<typeof settingsService.createLLM>[0]) => settingsService.createLLM(v),
    onSuccess: () => { message.success('创建成功'); qc.invalidateQueries({ queryKey: ['llm-configs'] }); closeModal() },
    onError: () => message.error('创建失败'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, v }: { id: number; v: Parameters<typeof settingsService.updateLLM>[1] }) =>
      settingsService.updateLLM(id, v),
    onSuccess: () => { message.success('更新成功'); qc.invalidateQueries({ queryKey: ['llm-configs'] }); closeModal() },
    onError: () => message.error('更新失败'),
  })

  const deleteMut = useMutation({
    mutationFn: settingsService.deleteLLM,
    onSuccess: () => { message.success('已删除'); qc.invalidateQueries({ queryKey: ['llm-configs'] }) },
    onError: () => message.error('删除失败'),
  })

  const testMut = useMutation({
    mutationFn: (id: number) => settingsService.testLLM(id),
    onSuccess: (res, id) => {
      setTestResult(prev => ({ ...prev, [id]: { ok: res.success, msg: res.message + (res.latency_ms ? ` (${res.latency_ms}ms)` : '') } }))
    },
  })

  const syncMut = useMutation({
    mutationFn: settingsService.syncLLM,
    onSuccess: () => { message.success('同步成功'); qc.invalidateQueries({ queryKey: ['llm-configs'] }) },
    onError: () => message.error('同步失败'),
  })

  function openCreate() { setEditing(null); form.resetFields(); setOpen(true) }
  function openEdit(r: LLMProviderConfig) {
    setEditing(r)
    form.setFieldsValue({ ...r, api_key: '' })
    setOpen(true)
  }
  function closeModal() { setOpen(false); setEditing(null); form.resetFields() }

  function submit() {
    form.validateFields().then(v => {
      if (!v.api_key) delete v.api_key
      if (editing) updateMut.mutate({ id: editing.id, v })
      else createMut.mutate(v)
    })
  }

  const cols = [
    { title: '名称', dataIndex: 'name', ellipsis: true },
    { title: '厂商', dataIndex: 'provider', width: 110, render: (v: string) => <Tag>{v}</Tag> },
    { title: '模型', dataIndex: 'model_name', ellipsis: true },
    { title: '角色', dataIndex: 'model_role', width: 100, render: (v: string) => <Tag color="blue">{v}</Tag> },
    {
      title: '默认', dataIndex: 'is_default', width: 60,
      render: (v: boolean) => v ? <CheckCircleOutlined style={{ color: '#52c41a' }} /> : null,
    },
    {
      title: '状态', dataIndex: 'is_enabled', width: 80,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '停用'}</Tag>,
    },
    {
      title: 'LiteLLM', dataIndex: 'litellm_synced', width: 90,
      render: (v: boolean) => <Tag color={v ? 'cyan' : 'orange'}>{v ? '已同步' : '未同步'}</Tag>,
    },
    {
      title: '连接测试', width: 160,
      render: (_: unknown, r: LLMProviderConfig) => {
        const res = testResult[r.id]
        return (
          <Space>
            <Button size="small" loading={testMut.isPending} onClick={() => testMut.mutate(r.id)}>
              测试
            </Button>
            {res && (
              res.ok
                ? <Text style={{ color: '#52c41a', fontSize: 12 }}>{res.msg}</Text>
                : <Text type="danger" style={{ fontSize: 12 }}>{res.msg}</Text>
            )}
          </Space>
        )
      },
    },
    {
      title: '操作', width: 160,
      render: (_: unknown, r: LLMProviderConfig) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
          <Tooltip title="同步到 LiteLLM">
            <Button size="small" icon={<SyncOutlined />} loading={syncMut.isPending} onClick={() => syncMut.mutate(r.id)} />
          </Tooltip>
          <Popconfirm title="确认删除？" onConfirm={() => deleteMut.mutate(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增 LLM 配置</Button>
        <Button icon={<ReloadOutlined />} onClick={() => qc.invalidateQueries({ queryKey: ['llm-configs'] })}>刷新</Button>
      </Space>
      <Alert
        type="info" showIcon style={{ marginBottom: 12 }}
        message="配置大模型接入参数后，系统将使用对应模型进行信息抽取（extraction）、内容生成（generation）、向量化（embedding）等任务。保存后自动同步到 LiteLLM Proxy。"
      />
      <Table loading={isLoading} dataSource={data} columns={cols} rowKey="id" size="small" />

      <Modal
        title={editing ? '编辑 LLM 配置' : '新增 LLM 配置'}
        open={open} onCancel={closeModal}
        onOk={submit}
        confirmLoading={createMut.isPending || updateMut.isPending}
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="显示名称" rules={[{ required: true }]}>
            <Input placeholder="如：Qwen生产环境" />
          </Form.Item>
          <Form.Item name="provider" label="厂商" rules={[{ required: true }]}>
            <Select>
              {PROVIDERS.map(p => <Option key={p} value={p}>{p}</Option>)}
            </Select>
          </Form.Item>
          <Form.Item name="model_name" label="模型名称" rules={[{ required: true }]}>
            <Input placeholder="如：qwen2.5-72b-instruct" />
          </Form.Item>
          <Form.Item name="api_key" label={editing ? 'API Key（留空不修改）' : 'API Key'}>
            <Input.Password placeholder="sk-..." />
          </Form.Item>
          <Form.Item name="api_base" label="API Base URL">
            <Input placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
          </Form.Item>
          <Form.Item name="model_role" label="模型角色" rules={[{ required: true }]} initialValue="general">
            <Select>
              {ROLES.map(r => <Option key={r} value={r}>{r}</Option>)}
            </Select>
          </Form.Item>
          <Form.Item name="max_tokens" label="Max Tokens" initialValue={4096}>
            <InputNumber min={256} max={128000} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="temperature" label="Temperature" initialValue={0.1}>
            <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
          </Form.Item>
          <Space>
            <Form.Item name="is_enabled" label="启用" valuePropName="checked" initialValue={true}>
              <Switch />
            </Form.Item>
            <Form.Item name="is_default" label="设为该角色默认" valuePropName="checked" initialValue={false}>
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </>
  )
}

// ── 数据源配置 Tab ─────────────────────────────────────────────────────────────

function DataSourceTab() {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<DataSourceConfig | null>(null)
  const [configText, setConfigText] = useState('{}')
  const [form] = Form.useForm()

  const { data = [], isLoading } = useQuery({
    queryKey: ['datasources'],
    queryFn: settingsService.listDataSources,
  })

  const { data: templates } = useQuery({
    queryKey: ['ds-templates'],
    queryFn: settingsService.getTemplates,
  })

  const createMut = useMutation({
    mutationFn: (v: Parameters<typeof settingsService.createDataSource>[0]) =>
      settingsService.createDataSource(v),
    onSuccess: () => { message.success('创建成功'); qc.invalidateQueries({ queryKey: ['datasources'] }); closeModal() },
    onError: () => message.error('创建失败'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, v }: { id: number; v: Parameters<typeof settingsService.updateDataSource>[1] }) =>
      settingsService.updateDataSource(id, v),
    onSuccess: () => { message.success('更新成功'); qc.invalidateQueries({ queryKey: ['datasources'] }); closeModal() },
    onError: () => message.error('更新失败'),
  })

  const deleteMut = useMutation({
    mutationFn: settingsService.deleteDataSource,
    onSuccess: () => { message.success('已删除'); qc.invalidateQueries({ queryKey: ['datasources'] }) },
    onError: () => message.error('删除失败'),
  })

  const triggerMut = useMutation({
    mutationFn: settingsService.triggerCollection,
    onSuccess: res => {
      message.success(`采集任务 #${res.task_id} 已提交`)
      qc.invalidateQueries({ queryKey: ['collection-tasks'] })
    },
    onError: () => message.error('触发失败'),
  })

  function openCreate() {
    setEditing(null)
    form.resetFields()
    setConfigText('{}')
    setOpen(true)
  }

  function openEdit(r: DataSourceConfig) {
    setEditing(r)
    form.setFieldsValue({ ...r })
    setConfigText(JSON.stringify(r.config_json, null, 2))
    setOpen(true)
  }

  function closeModal() { setOpen(false); setEditing(null) }

  function applyTemplate(type: string) {
    const tpl = (templates as Record<string, unknown>)?.[type]
    if (tpl) setConfigText(JSON.stringify(tpl, null, 2))
  }

  function submit() {
    form.validateFields().then(v => {
      let cfg: Record<string, unknown> = {}
      try { cfg = JSON.parse(configText) } catch { message.error('配置 JSON 格式错误'); return }
      const payload = { ...v, config_json: cfg }
      if (editing) updateMut.mutate({ id: editing.id, v: payload })
      else createMut.mutate(payload)
    })
  }

  const cols = [
    { title: '名称', dataIndex: 'name', ellipsis: true },
    { title: '类型', dataIndex: 'source_type', width: 120, render: (v: string) => <Tag>{v}</Tag> },
    { title: '画像类型', dataIndex: 'profile_type', width: 100, render: (v: string) => <Tag color="purple">{v}</Tag> },
    { title: '定时', dataIndex: 'schedule_cron', width: 120, render: (v: string | null) => v ?? <Text type="secondary">手动</Text> },
    {
      title: '上次运行', dataIndex: 'last_run_at', width: 160,
      render: (v: string | null, r: DataSourceConfig) => v ? (
        <Space>
          <Tag color={r.last_run_status === 'success' ? 'green' : r.last_run_status === 'failed' ? 'red' : 'orange'}>
            {r.last_run_status}
          </Tag>
          <Text style={{ fontSize: 11 }}>{v.slice(0, 16).replace('T', ' ')}</Text>
        </Space>
      ) : <Text type="secondary">从未</Text>,
    },
    {
      title: '状态', dataIndex: 'is_enabled', width: 80,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '停用'}</Tag>,
    },
    {
      title: '操作', width: 160,
      render: (_: unknown, r: DataSourceConfig) => (
        <Space>
          <Tooltip title="立即采集">
            <Button
              size="small" type="primary" icon={<PlayCircleOutlined />}
              loading={triggerMut.isPending}
              onClick={() => triggerMut.mutate(r.id)}
              disabled={!r.is_enabled}
            />
          </Tooltip>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
          <Popconfirm title="确认删除？" onConfirm={() => deleteMut.mutate(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增数据源</Button>
        <Button icon={<ReloadOutlined />} onClick={() => qc.invalidateQueries({ queryKey: ['datasources'] })}>刷新</Button>
      </Space>
      <Alert
        type="info" showIcon style={{ marginBottom: 12 }}
        message="配置外部数据源后，点击▶触发采集，系统自动拉取数据并导入对应画像库。支持 REST API、RSS Feed、NSFC、CNIPA专利等类型。"
      />
      <Table loading={isLoading} dataSource={data} columns={cols} rowKey="id" size="small" />

      <Modal
        title={editing ? '编辑数据源' : '新增数据源'}
        open={open} onCancel={closeModal} onOk={submit}
        confirmLoading={createMut.isPending || updateMut.isPending}
        width={680}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如：NSFC量子计算项目" />
          </Form.Item>
          <Space style={{ width: '100%' }} align="start">
            <Form.Item name="source_type" label="数据源类型" rules={[{ required: true }]} style={{ width: 200 }}>
              <Select onChange={applyTemplate}>
                {SOURCE_TYPES.map(t => <Option key={t} value={t}>{t}</Option>)}
              </Select>
            </Form.Item>
            <Form.Item name="profile_type" label="导入画像类型" rules={[{ required: true }]} style={{ width: 200 }}>
              <Select>
                {PROFILE_TYPES.map(t => <Option key={t} value={t}>{t}</Option>)}
              </Select>
            </Form.Item>
          </Space>
          <Form.Item name="schedule_cron" label="定时采集（cron，留空为手动）">
            <Input placeholder="0 2 * * *  →  每天凌晨2点" />
          </Form.Item>
          <Form.Item name="is_enabled" label="启用" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
          <Form.Item label="数据源配置（JSON）">
            <Text type="secondary" style={{ fontSize: 12 }}>选择类型后自动填入模板，按需修改</Text>
            <TextArea
              value={configText}
              onChange={e => setConfigText(e.target.value)}
              rows={14}
              style={{ fontFamily: 'monospace', fontSize: 12 }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}

// ── 采集任务 Tab ──────────────────────────────────────────────────────────────

function TasksTab() {
  const qc = useQueryClient()
  const [logDrawer, setLogDrawer] = useState<CollectionTask | null>(null)

  const { data = [], isLoading } = useQuery({
    queryKey: ['collection-tasks'],
    queryFn: () => settingsService.listTasks(),
    refetchInterval: 5000, // 5秒轮询
  })

  const cols = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '数据源', dataIndex: 'source_name', ellipsis: true },
    { title: '画像类型', dataIndex: 'profile_type', width: 100, render: (v: string) => <Tag color="purple">{v}</Tag> },
    { title: '状态', dataIndex: 'status', width: 110, render: statusBadge },
    { title: '获取', dataIndex: 'records_fetched', width: 70, render: (v: number) => <Text>{v}</Text> },
    { title: '导入', dataIndex: 'records_imported', width: 70, render: (v: number) => <Text style={{ color: '#52c41a' }}>{v}</Text> },
    {
      title: '开始时间', dataIndex: 'started_at', width: 150,
      render: (v: string | null) => v ? v.slice(0, 19).replace('T', ' ') : '-',
    },
    {
      title: '耗时', width: 80,
      render: (_: unknown, r: CollectionTask) => {
        if (!r.started_at || !r.completed_at) return '-'
        const ms = new Date(r.completed_at).getTime() - new Date(r.started_at).getTime()
        return `${(ms / 1000).toFixed(1)}s`
      },
    },
    {
      title: '操作', width: 90,
      render: (_: unknown, r: CollectionTask) => (
        <Button size="small" onClick={() => setLogDrawer(r)}>日志</Button>
      ),
    },
  ]

  return (
    <>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ReloadOutlined />} onClick={() => qc.invalidateQueries({ queryKey: ['collection-tasks'] })}>刷新</Button>
        <Text type="secondary" style={{ fontSize: 12 }}>每5秒自动刷新</Text>
      </Space>
      <Table loading={isLoading} dataSource={data} columns={cols} rowKey="id" size="small" />

      <Drawer
        title={`采集日志 #${logDrawer?.id} — ${logDrawer?.source_name}`}
        open={!!logDrawer}
        onClose={() => setLogDrawer(null)}
        width={600}
      >
        {logDrawer && (
          <>
            <Descriptions column={2} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="状态">{statusBadge(logDrawer.status)}</Descriptions.Item>
              <Descriptions.Item label="画像类型">{logDrawer.profile_type}</Descriptions.Item>
              <Descriptions.Item label="获取">{logDrawer.records_fetched}</Descriptions.Item>
              <Descriptions.Item label="导入">{logDrawer.records_imported}</Descriptions.Item>
            </Descriptions>
            {logDrawer.error_msg && (
              <Alert type="error" message={logDrawer.error_msg} style={{ marginBottom: 12 }} />
            )}
            <div style={{
              background: '#141414', color: '#d4d4d4', padding: 12, borderRadius: 4,
              fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap', maxHeight: 480, overflow: 'auto',
            }}>
              {logDrawer.log_text || '（无日志）'}
            </div>
          </>
        )}
      </Drawer>
    </>
  )
}

// ── 主页面 ─────────────────────────────────────────────────────────────────────

export default function Settings() {
  return (
    <Tabs
      defaultActiveKey="llm"
      items={[
        { key: 'llm',        label: <><ApiOutlined />大模型配置</>,   children: <LLMTab /> },
        { key: 'datasource', label: <><PlayCircleOutlined />数据源配置</>, children: <DataSourceTab /> },
        { key: 'tasks',      label: <><SyncOutlined />采集任务</>,     children: <TasksTab /> },
      ]}
    />
  )
}
