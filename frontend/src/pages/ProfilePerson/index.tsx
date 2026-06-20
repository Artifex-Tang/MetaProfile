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
} from 'antd'
import { SearchOutlined, ReloadOutlined, UploadOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { personService } from '../../api/profile'
import type { PersonProfile, PersonSearchItem, RelationItem } from '../../api/types'

const { Search } = Input
const { Text } = Typography

function DetailDrawer({ id, open, onClose, selfType }: { id: string; open: boolean; onClose: () => void; selfType: string }) {
  const profile = useQuery({
    queryKey: ['person', id],
    queryFn: () => personService.getById(id),
    enabled: open && !!id,
  })
  const relations = useQuery({
    queryKey: ['person-relations', id],
    queryFn: () => personService.getRelations(id),
    enabled: open && !!id,
  })
  const p = profile.data
  const { ctx, handleNodeClick } = useCrossProfileJump(selfType, id, p?.name_cn ?? null)

  const qc = useQueryClient()
  const [enrichTaskId, setEnrichTaskId] = useState<string | null>(null)
  const enrichMut = useMutation({
    mutationFn: () => personService.enrich(id),
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
    queryKey: ['person-enrich-task', enrichTaskId],
    queryFn: () => personService.getEnrichTaskStatus(enrichTaskId!),
    enabled: !!enrichTaskId,
    refetchInterval: (q) => isEnrichTerminal(q.state.data?.status) ? false : 2000,
  })
  useEffect(() => {
    const st = enrichStatus.data?.status
    if (!st || !isEnrichTerminal(st)) return
    if (st === 'done') {
      message.success('LLM补全完成')
      qc.invalidateQueries({ queryKey: ['person', id] })
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
    <Drawer title={drawerTitle} width={680} open={open} onClose={onClose} destroyOnClose>
      {profile.isLoading ? <Spin /> : profile.isError ? <Alert type="error" message="加载失败" /> : p && (
        <>
        <JumpBreadcrumb ctx={ctx} />
        <Tabs items={[
          {
            key: 'info', label: '基本信息',
            children: (
              <>
              <Descriptions column={1} size="small" bordered>
                <Descriptions.Item label="姓名（中）">{p.name_cn}</Descriptions.Item>
                <Descriptions.Item label="姓名（英）">{p.name_en ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="性别">{p.gender ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="国籍">{p.nationality ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="出生日期">{p.birth_date ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="当前机构">{p.current_org ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="当前职务">
                  {p.current_position.map((pos, i) => <Tag key={i}>{pos}</Tag>)}
                </Descriptions.Item>
                <Descriptions.Item label="最高学历">{p.highest_degree ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="人员类别">{p.person_category ?? '-'}</Descriptions.Item>
                <Descriptions.Item label="专业领域">
                  {p.professional_domains.map(d => <Tag key={d} color="blue">{d}</Tag>)}
                </Descriptions.Item>
                {p.professional_skills.length > 0 && (
                  <Descriptions.Item label="专业技能">
                    {p.professional_skills.map(s => <Tag key={s}>{s}</Tag>)}
                  </Descriptions.Item>
                )}
                <Descriptions.Item label="简介">
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
            key: 'career', label: `工作经历 (${p.careers.length})`,
            children: p.careers.length === 0
              ? <Text type="secondary">暂无工作经历</Text>
              : (
                <Timeline
                  mode="left"
                  items={p.careers.map((c, i) => ({
                    key: i,
                    label: `${c.start_date}${c.end_date ? ' — ' + c.end_date : ' — 至今'}`,
                    children: (
                      <div>
                        <Text strong>{c.org}</Text>
                        {c.enterprise && <div style={{ color: '#595959' }}>{c.enterprise}</div>}
                        {c.position && <Tag color="geekblue" style={{ marginTop: 4 }}>{c.position}</Tag>}
                      </div>
                    ),
                  }))}
                />
              ),
          },
          {
            key: 'education', label: `教育经历 (${p.educations.length})`,
            children: p.educations.length === 0
              ? <Text type="secondary">暂无教育经历</Text>
              : (
                <Timeline
                  mode="left"
                  items={p.educations.map((e, i) => ({
                    key: i,
                    label: e.degree_date ?? e.start_date ?? '-',
                    children: (
                      <div>
                        <Text strong>{e.school ?? '-'}</Text>
                        <div style={{ color: '#595959' }}>
                          {[e.degree, e.major].filter(Boolean).join(' · ')}
                        </div>
                      </div>
                    ),
                  }))}
                />
              ),
          },
          {
            key: 'outputs', label: `学术成果 (${p.academic_outputs.length})`,
            children: p.academic_outputs.length === 0
              ? <Text type="secondary">暂无学术成果</Text>
              : (
                <Table
                  size="small"
                  dataSource={p.academic_outputs}
                  rowKey={(_, i) => String(i)}
                  pagination={{ pageSize: 8 }}
                  columns={[
                    { title: '成果名称', dataIndex: 'name', ellipsis: true, render: v => v ?? '-' },
                    { title: '类型', dataIndex: 'form', width: 80, render: v => v ? <Tag>{v}</Tag> : '-' },
                    { title: '发布时间', dataIndex: 'publish_date', width: 110, render: v => v ?? '-' },
                    { title: '作者排名', dataIndex: 'rank', width: 100, render: v => v ?? '-' },
                    { title: '引用数', dataIndex: 'citations', width: 70, render: v => v ?? '-' },
                  ]}
                />
              ),
          },
          {
            key: 'focuses', label: `技术关注 (${p.tech_focuses.length})`,
            children: p.tech_focuses.length === 0
              ? <Text type="secondary">暂无数据</Text>
              : p.tech_focuses.map((f, i) => (
                <div key={i} style={{ marginBottom: 16 }}>
                  <div style={{ marginBottom: 4 }}>
                    {f.content.map((c, j) => <Tag key={j} color="purple">{c}</Tag>)}
                  </div>
                  {f.consistency_with_policy && (
                    <div style={{ color: '#595959', fontSize: 12 }}>与政策一致性: {f.consistency_with_policy}</div>
                  )}
                  {f.potential_impact.length > 0 && (
                    <div style={{ fontSize: 12 }}>潜在影响: {f.potential_impact.join('；')}</div>
                  )}
                </div>
              )),
          },
          {
            key: 'graph', label: '关联图谱',
            children: relations.isLoading ? <Spin /> : relations.isError ? <Alert type="error" message="加载失败" /> : (
              relations.data && relations.data.items.length > 0
                ? <RelationGraph relations={relations.data.items} selfLabel="当前人员" onNodeClick={handleNodeClick} navTypes={NAV_TYPES} />
                : <Text type="secondary">暂无关联数据</Text>
            ),
          },
        ]} />
        </>
      )}
    </Drawer>
  )
}

export default function ProfilePerson() {
  const qc = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const { id: routeId } = useParams()
  const [selectedId, setSelectedId] = useState<string | null>(routeId ?? null)
  useEffect(() => { if (routeId) setSelectedId(routeId) }, [routeId])

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['person-search', keyword, page, pageSize],
    queryFn: () => personService.search(keyword, page, pageSize),
  })

  const importMut = useMutation({
    mutationFn: (profiles: Partial<PersonProfile>[]) => personService.bulkImport(profiles),
    onSuccess: () => {
      message.success('导入成功')
      qc.invalidateQueries({ queryKey: ['person-search'] })
    },
    onError: () => message.error('导入失败'),
  })

  const cols = [
    { title: '姓名', dataIndex: 'person_name_cn', ellipsis: true,
      render: (v: string, r: PersonSearchItem) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => setSelectedId(r.person_id)}>{v}</Button>
      ) },
    {
      title: '专业领域',
      dataIndex: 'person_domain',
      render: (d: string[]) => d?.slice(0, 2).map(t => <Tag key={t}>{t}</Tag>),
    },
    {
      title: '操作',
      width: 80,
      render: (_: unknown, r: PersonSearchItem) => (
        <Button type="link" size="small" onClick={() => setSelectedId(r.person_id)}>详情</Button>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Search
          placeholder="搜索人员姓名或领域"
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
        rowKey="person_id"
        size="small"
        pagination={{
          current: page, pageSize, total: data?.total,
          showSizeChanger: true, pageSizeOptions: [10, 20, 50, 100],
          onChange: (p, ps) => { setPage(p); setPageSize(ps) }, showTotal: t => `共 ${t} 条`,
        }}
        onRow={r => ({ onDoubleClick: () => setSelectedId(r.person_id) })}
      />

      {selectedId && (
        <DetailDrawer key={selectedId} selfType="person" id={selectedId} open={!!selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  )
}
