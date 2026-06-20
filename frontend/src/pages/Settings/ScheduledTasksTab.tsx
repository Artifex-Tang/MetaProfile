import { useState } from 'react'
import { Table, Button, Tag, Space, Modal, Form, Input, Select, Switch, message, Popconfirm } from 'antd'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsService, type ScheduledTask } from '../../api/settings'

const TASK_TYPES = [
  { value: 'translate_batch', label: '批量翻译' },
  { value: 'collection', label: '采集' },
]

const STATUS_COLOR: Record<string, string> = {
  ok: 'green', failed: 'red', running: 'blue', pending: 'default',
}

export default function ScheduledTasksTab() {
  const qc = useQueryClient()
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const list = useQuery({
    queryKey: ['scheduled-tasks'],
    queryFn: settingsService.listScheduledTasks,
    refetchInterval: 5000,
  })

  const createMut = useMutation({
    mutationFn: settingsService.createScheduledTask,
    onSuccess: () => { message.success('已创建'); setModalOpen(false); form.resetFields(); qc.invalidateQueries({ queryKey: ['scheduled-tasks'] }) },
    onError: (e: unknown) => message.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? '创建失败'),
  })
  const runMut = useMutation({
    mutationFn: (id: number) => settingsService.runScheduledTask(id),
    onSuccess: (r) => message.success(r.queued ? `已入队 ${r.task_id}` : '入队失败'),
    onError: () => message.error('执行失败'),
  })
  const delMut = useMutation({
    mutationFn: (id: number) => settingsService.deleteScheduledTask(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['scheduled-tasks'] }) },
  })
  const batchTranslateMut = useMutation({
    mutationFn: () => settingsService.translateBatch(),
    onSuccess: (r) => message.success(`批量翻译已入队 ${r.task_id}`),
    onError: () => message.error('批量翻译失败'),
  })

  const cols = [
    { title: '名称', dataIndex: 'name' },
    { title: '类型', dataIndex: 'task_type', render: (v: string) => TASK_TYPES.find(t => t.value === v)?.label ?? v },
    { title: 'Cron', dataIndex: 'cron', render: (v: string) => <code>{v}</code> },
    { title: '启用', dataIndex: 'enabled', render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '是' : '否'}</Tag> },
    { title: '上次运行', dataIndex: 'last_run_at', render: (v: string | null) => v ?? '-' },
    { title: '状态', dataIndex: 'last_status', render: (v: string) => <Tag color={STATUS_COLOR[v] ?? 'default'}>{v}</Tag> },
    {
      title: '操作', render: (_: unknown, r: ScheduledTask) => (
        <Space>
          <Button size="small" onClick={() => runMut.mutate(r.id)} loading={runMut.isPending}>立即执行</Button>
          <Popconfirm title="删除该定时任务？" onConfirm={() => delMut.mutate(r.id)}>
            <Button size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Button type="primary" onClick={() => setModalOpen(true)}>新建定时任务</Button>
        <Popconfirm title="批量翻译所有 name_cn 空的实体？" onConfirm={() => batchTranslateMut.mutate()}>
          <Button loading={batchTranslateMut.isPending}>批量翻译（立即）</Button>
        </Popconfirm>
      </Space>
      <Table
        rowKey="id" size="small" columns={cols} dataSource={list.data}
        loading={list.isLoading} pagination={false}
      />
      <Modal
        title="新建定时任务" open={modalOpen} onCancel={() => setModalOpen(false)}
        onOk={() => form.validateFields().then(v => createMut.mutate(v))}
        confirmLoading={createMut.isPending}
      >
        <Form form={form} layout="vertical" initialValues={{ task_type: 'translate_batch', enabled: true, params: '{}' }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input placeholder="nightly-translate" /></Form.Item>
          <Form.Item name="task_type" label="类型" rules={[{ required: true }]}>
            <Select options={TASK_TYPES} />
          </Form.Item>
          <Form.Item name="cron" label="Cron（5 段）" rules={[{ required: true }]} extra="如 0 2 * * *（每天 2 点）">
            <Input placeholder="0 2 * * *" />
          </Form.Item>
          <Form.Item name="params" label="参数 JSON"><Input placeholder='{"entity_type":"tech"}' /></Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked"><Switch /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
