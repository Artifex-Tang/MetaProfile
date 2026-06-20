import { useState, useRef, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import RelationGraph from '../../components/RelationGraph'
import JumpBreadcrumb from '../../components/JumpBreadcrumb'
import DataQualityCard from '../../components/DataQualityCard'
import { useCrossProfileJump, NAV_TYPES } from '../../utils/crossProfile'
import { enrichStatusLabel, isEnrichTerminal } from '../../utils/enrichStatus'
import {
  Input, Button, Table, Tag, Drawer, Tabs, Spin, Alert,
  Descriptions, Space, Typography, Upload, message, Timeline,
  Card, Row, Col, Statistic,
} from 'antd'
import { SearchOutlined, ReloadOutlined, UploadOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { orgService } from '../../api/profile'
import type { OrgProfile, OrgSearchItem, RelationItem } from '../../api/types'

const { Search } = Input
const { Text } = Typography

function DetailDrawer({ id, open, onClose, selfType }: { id: string; open: boolean; onClose: () => void; selfType: string }) {
  const profile = useQuery({
    queryKey: ['org', id],
    queryFn: () => orgService.getById(id),
    enabled: open && !!id,
  })
  const relations = useQuery({
    queryKey: ['org-relations', id],
    queryFn: () => orgService.getRelations(id),
    enabled: open && !!id,
  })
  const p = profile.data
  const { ctx, handleNodeClick } = useCrossProfileJump(selfType, id, p?.name_cn ?? null)

  const qc = useQueryClient()
  const [enrichTaskId, setEnrichTaskId] = useState<string | null>(null)
  const enrichMut = useMutation({
    mutationFn: () => orgService.enrich(id),
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
    queryKey: ['org-enrich-task', enrichTaskId],
    queryFn: () => orgService.getEnrichTaskStatus(enrichTaskId!),
    enabled: !!enrichTaskId,
    refetchInterval: (q) => isEnrichTerminal(q.state.data?.status) ? false : 2000,
  })
  useEffect(() => {
    const st = enrichStatus.data?.status
    if (!st || !isEnrichTerminal(st)) return
    if (st === 'done') {
      message.success('LLM补全完成')
      qc.invalidateQueries({ queryKey: ['org', id] })
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
      <span>{p?.name_cn ?? id}</span>
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
                <Descriptions.Item label="机构名（中）">{p.name_cn}</Descriptions.Item>
                <Descriptions.Item label="机构名（英）">{p.name_en ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="国家/地区">{p.country ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="成立时间">{p.founded_date ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="机构类型">
                  {p.org_types.map(t => <Tag key={t} color="blue">{t}</Tag>)}
                </Descriptions.Item>
                <Descriptions.Item label="机构规模">{p.scale != null ? `${p.scale} 人` : '-'}</Descriptions.Item>
                <Descriptions.Item label="技术领域">
                  {p.tech_domains.map(d => <Tag key={d}>{d}</Tag>)}
                </Descriptions.Item>
                <Descriptions.Item label="机构职能">
                  <Text style={{ whiteSpace: 'pre-wrap' }}>{p.function ?? '-'}</Text>
                </Descriptions.Item>
                <Descriptions.Item label="机构简介">
                  <Text style={{ whiteSpace: 'pre-wrap' }}>{p.summary ?? '-'}</Text>
                </Descriptions.Item>
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
            key: 'history', label: `发展沿革 (${p.histories.length})`,
            children: p.histories.length === 0
              ? <Text type="secondary">暂无沿革数据</Text>
              : (
                <Timeline
                  mode="left"
                  items={p.histories.map((h, i) => ({
                    key: i,
                    label: h.change_date,
                    children: <Text>{h.change_description}</Text>,
                  }))}
                />
              ),
          },
          {
            key: 'team', label: '科研队伍',
            children: (
              <Space direction="vertical" style={{ width: '100%' }} size={16}>
                {p.team ? (
                  <Card title="队伍概况" size="small">
                    <Row gutter={16}>
                      {p.team.team_size != null && (
                        <Col span={8}><Statistic title="队伍规模" value={p.team.team_size} suffix="人" /></Col>
                      )}
                      {p.team.talent_type && (
                        <Col span={16}><Statistic title="人才类型" value={p.team.talent_type} /></Col>
                      )}
                    </Row>
                    {p.team.top_talents.length > 0 && (
                      <div style={{ marginTop: 12 }}>
                        <Text type="secondary">顶尖人才: </Text>
                        {p.team.top_talents.map(t => <Tag key={t} color="gold">{t}</Tag>)}
                      </div>
                    )}
                  </Card>
                ) : <Text type="secondary">暂无队伍数据</Text>}
                <Card title={`科研设施 (${p.facilities.length})`} size="small">
                  {p.facilities.length === 0
                    ? <Text type="secondary">暂无数据</Text>
                    : (
                      <Table
                        size="small"
                        dataSource={p.facilities}
                        rowKey={(_, i) => String(i)}
                        pagination={false}
                        columns={[
                          { title: '设施名称', dataIndex: 'name', ellipsis: true, render: v => v ?? '-' },
                          { title: '用途', dataIndex: 'purpose', ellipsis: true, render: v => v ?? '-' },
                          { title: '状态', dataIndex: 'experiment_status', width: 100, render: v => v ?? '-' },
                          { title: '建设时间', dataIndex: 'launch_date', width: 110, render: v => v ?? '-' },
                        ]}
                      />
                    )}
                </Card>
              </Space>
            ),
          },
          {
            key: 'outputs', label: `主要成果 (${p.outputs.length})`,
            children: p.outputs.length === 0
              ? <Text type="secondary">暂无成果数据</Text>
              : (
                <Table
                  size="small"
                  dataSource={p.outputs}
                  rowKey={(_, i) => String(i)}
                  pagination={{ pageSize: 8 }}
                  columns={[
                    { title: '成果名称', dataIndex: 'name', ellipsis: true, render: v => v ?? '-' },
                    { title: '类型', dataIndex: 'form', width: 80, render: v => v ? <Tag>{v}</Tag> : '-' },
                    { title: '作者', dataIndex: 'author', width: 100, render: v => v ?? '-' },
                    { title: '发布时间', dataIndex: 'publish_date', width: 110, render: v => v ?? '-' },
                  ]}
                />
              ),
          },
          {
            key: 'awards', label: `荣誉奖励 (${p.awards.length})`,
            children: p.awards.length === 0
              ? <Text type="secondary">暂无奖励数据</Text>
              : (
                <Table
                  size="small"
                  dataSource={p.awards}
                  rowKey={(_, i) => String(i)}
                  pagination={false}
                  columns={[
                    { title: '奖项名称', dataIndex: 'name', ellipsis: true, render: v => v ?? '-' },
                    { title: '类型', dataIndex: 'award_type', width: 100, render: v => v ?? '-' },
                    { title: '级别', dataIndex: 'level', width: 80, render: v => v ?? '-' },
                    { title: '获奖时间', dataIndex: 'award_date', width: 110, render: v => v ?? '-' },
                  ]}
                />
              ),
          },
          {
            key: 'graph', label: '关联图谱',
            children: relations.isLoading ? <Spin /> : relations.isError ? <Alert type="error" message="加载失败" /> : (
              relations.data && relations.data.items.length > 0
                ? <RelationGraph relations={relations.data.items} selfLabel="当前机构" onNodeClick={handleNodeClick} navTypes={NAV_TYPES} />
                : <Text type="secondary">暂无关联数据</Text>
            ),
          },
        ]} />
        </>
      )}
    </Drawer>
  )
}

export default function ProfileOrg() {
  const qc = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const { id: routeId } = useParams()
  const [selectedId, setSelectedId] = useState<string | null>(routeId ?? null)
  useEffect(() => { if (routeId) setSelectedId(routeId) }, [routeId])

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['org-search', keyword, page, pageSize],
    queryFn: () => orgService.search(keyword, page, pageSize),
  })

  const importMut = useMutation({
    mutationFn: (profiles: Partial<OrgProfile>[]) => orgService.bulkImport(profiles),
    onSuccess: () => {
      message.success('导入成功')
      qc.invalidateQueries({ queryKey: ['org-search'] })
    },
    onError: () => message.error('导入失败'),
  })

  const cols = [
    { title: '机构名称', dataIndex: 'org_name_cn', ellipsis: true,
      render: (v: string, r: OrgSearchItem) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => setSelectedId(r.org_id)}>{v}</Button>
      ) },
    {
      title: '技术领域',
      dataIndex: 'org_domain',
      render: (d: string[]) => d?.slice(0, 2).map(t => <Tag key={t}>{t}</Tag>),
    },
    {
      title: '操作',
      width: 80,
      render: (_: unknown, r: OrgSearchItem) => (
        <Button type="link" size="small" onClick={() => setSelectedId(r.org_id)}>详情</Button>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Search
          placeholder="搜索机构名称或领域"
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
        rowKey="org_id"
        size="small"
        pagination={{
          current: page, pageSize, total: data?.total,
          showSizeChanger: true, pageSizeOptions: [10, 20, 50, 100],
          onChange: (p, ps) => { setPage(p); setPageSize(ps) }, showTotal: t => `共 ${t} 条`,
        }}
        onRow={r => ({ onDoubleClick: () => setSelectedId(r.org_id) })}
      />

      {selectedId && (
        <DetailDrawer key={selectedId} selfType="org" id={selectedId} open={!!selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  )
}
