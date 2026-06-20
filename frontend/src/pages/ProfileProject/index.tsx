import { useState, useRef, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import RelationGraph from '../../components/RelationGraph'
import JumpBreadcrumb from '../../components/JumpBreadcrumb'
import DataQualityCard from '../../components/DataQualityCard'
import { useCrossProfileJump, NAV_TYPES } from '../../utils/crossProfile'
import { enrichStatusLabel, isEnrichTerminal } from '../../utils/enrichStatus'
import {
  Input, Button, Table, Tag, Drawer, Tabs, Spin, Alert,
  Descriptions, Space, Typography, Upload, message, Timeline, Card,
} from 'antd'
import { SearchOutlined, ReloadOutlined, UploadOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectService } from '../../api/profile'
import type { ProjectProfile, ProjectSearchItem, RelationItem } from '../../api/types'

const { Search } = Input
const { Text } = Typography

function DetailDrawer({ id, open, onClose, selfType }: { id: string; open: boolean; onClose: () => void; selfType: string }) {
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
  const { ctx, handleNodeClick } = useCrossProfileJump(selfType, id, p?.name_cn?.[0] ?? null)

  const primaryName = p?.name_cn?.[0] ?? id

  const qc = useQueryClient()
  const [enrichTaskId, setEnrichTaskId] = useState<string | null>(null)
  const enrichMut = useMutation({
    mutationFn: () => projectService.enrich(id),
    onSuccess: (res) => {
      if (res.status === 'skipped') {
        message.info('完整度充足，无需补全')
        return
      }
      setEnrichTaskId(res.task_id)
      message.loading({ content: 'LLM补全任务已提交，执行中...', key: 'enrich', duration: 2 })
    },
    onError: () => message.error('提交补全任务失败'),
  })
  const enrichStatus = useQuery({
    queryKey: ['project-enrich-task', enrichTaskId],
    queryFn: () => projectService.getEnrichTaskStatus(enrichTaskId!),
    enabled: !!enrichTaskId,
    refetchInterval: (q) => isEnrichTerminal(q.state.data?.status) ? false : 2000,
  })
  useEffect(() => {
    const st = enrichStatus.data?.status
    if (!st || !isEnrichTerminal(st)) return
    if (st === 'done') {
      message.success('LLM补全完成')
      qc.invalidateQueries({ queryKey: ['project', id] })
    } else if (st === 'skipped') {
      message.info('完整度充足，无需补全')
    } else if (st === 'no_fill') {
      message.info('无字段可补')
    } else {
      message.error(`补全${enrichStatusLabel(st)}`)
    }
    setEnrichTaskId(null)
  }, [enrichStatus.data?.status])

  const drawerTitle = (
    <Space>
      <span>{primaryName}</span>
      <Button
        size="small"
        icon={<ThunderboltOutlined />}
        loading={enrichMut.isPending || (!!enrichTaskId && !isEnrichTerminal(enrichStatus.data?.status))}
        onClick={() => enrichMut.mutate()}
      >
        {enrichTaskId ? enrichStatusLabel(enrichStatus.data?.status) : 'LLM补全'}
      </Button>
    </Space>
  )

  return (
    <Drawer title={drawerTitle} width={700} open={open} onClose={onClose} destroyOnClose>
      {profile.isLoading ? <Spin /> : profile.isError ? <Alert type="error" message="加载失败" /> : p && (
        <>
        <JumpBreadcrumb ctx={ctx} />
        <Tabs items={[
          {
            key: 'info', label: '基本信息',
            children: (
              <>
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
              <DataQualityCard
                veracityScore={p.veracity_score}
                timelinessScore={p.timeliness_score}
                dataAsOf={p.data_as_of}
              />
              </>
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
                ? <RelationGraph relations={relations.data.items} selfLabel="当前项目" onNodeClick={handleNodeClick} navTypes={NAV_TYPES} />
                : <Text type="secondary">暂无关联数据</Text>
            ),
          },
        ]} />
        </>
      )}
    </Drawer>
  )
}

export default function ProfileProject() {
  const qc = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const { id: routeId } = useParams()
  const [selectedId, setSelectedId] = useState<string | null>(routeId ?? null)
  useEffect(() => { if (routeId) setSelectedId(routeId) }, [routeId])

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['project-search', keyword, page, pageSize],
    queryFn: () => projectService.search(keyword, page, pageSize),
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
    {
      title: '项目名称',
      dataIndex: 'project_name_cn',
      ellipsis: true,
      render: (v: string | string[], r: ProjectSearchItem) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => setSelectedId(r.project_id)}>
          {Array.isArray(v) ? (v[0] ?? '-') : (v ?? '-')}
        </Button>
      ),
    },
    {
      title: '技术领域',
      dataIndex: 'project_domain',
      render: (d: string[]) => d?.slice(0, 2).map(t => <Tag key={t}>{t}</Tag>),
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
          current: page, pageSize, total: data?.total,
          showSizeChanger: true, pageSizeOptions: [10, 20, 50, 100],
          onChange: (p, ps) => { setPage(p); setPageSize(ps) }, showTotal: t => `共 ${t} 条`,
        }}
        onRow={r => ({ onDoubleClick: () => setSelectedId(r.project_id) })}
      />

      {selectedId && (
        <DetailDrawer key={selectedId} selfType="project" id={selectedId} open={!!selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  )
}
