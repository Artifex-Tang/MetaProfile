import { Row, Col, Card, Statistic, Table, Tag, Spin, Alert } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { techService } from '../../api/tech'
import { projectService, orgService, personService } from '../../api/profile'
import { scanService } from '../../api/scan'
import type { FrontierTechItem, AlertItem } from '../../api/types'

const severityColor = (s: string) =>
  s === 'critical' ? 'red' : s === 'warn' ? 'orange' : 'blue'
const severityLabel = (s: string) =>
  ({ critical: '严重', warn: '警告', info: '信息' } as Record<string, string>)[s] ?? s
const frontierStatusLabel = (s: string) =>
  ({ validated: '已验证', pending: '待验证', rejected: '已排除' } as Record<string, string>)[s] ?? s
const alertTypeLabel = (s: string) =>
  ({ burst: '突现', trl_upgrade: 'TRL升级', org_layout: '机构布局' } as Record<string, string>)[s] ?? s

export default function Dashboard() {
  const nav = useNavigate()
  const techStats    = useQuery({ queryKey: ['stats', 'tech'],    queryFn: techService.getStats })
  const projectStats = useQuery({ queryKey: ['stats', 'project'], queryFn: projectService.getStats })
  const orgStats     = useQuery({ queryKey: ['stats', 'org'],     queryFn: orgService.getStats })
  const personStats  = useQuery({ queryKey: ['stats', 'person'],  queryFn: personService.getStats })
  const frontier     = useQuery({ queryKey: ['frontier', 'top5'], queryFn: () => scanService.listFrontierTech(1, 5) })
  const alerts       = useQuery({ queryKey: ['alerts', 'top5'],   queryFn: () => scanService.listAlerts(1, 5) })

  const statsCards = [
    { title: '技术画像', value: techStats.data?.total ?? '-',    color: '#1677ff', route: '/tech' },
    { title: '项目画像', value: projectStats.data?.total ?? '-', color: '#52c41a', route: '/project' },
    { title: '机构画像', value: orgStats.data?.total ?? '-',     color: '#fa8c16', route: '/org' },
    { title: '人员画像', value: personStats.data?.total ?? '-',  color: '#722ed1', route: '/person' },
  ]

  const frontierCols = [
    { title: '技术名称', dataIndex: 'tech_name', ellipsis: true },
    { title: '领域', dataIndex: 'tech_domain', render: (d: string[]) => d.slice(0, 1).join('') },
    { title: '融合评分', dataIndex: 'fusion_score', render: (v: number) => v.toFixed(3),
      sorter: (a: FrontierTechItem, b: FrontierTechItem) => a.fusion_score - b.fusion_score },
    { title: 'TRL', dataIndex: 'trl_level', render: (v: number | null) => v ?? '-' },
    { title: '状态', dataIndex: 'status',
      render: (v: string) => <Tag color={v === 'validated' ? 'green' : 'default'}>{frontierStatusLabel(v)}</Tag> },
  ]

  const alertCols = [
    { title: '技术', dataIndex: 'tech_name', ellipsis: true },
    { title: '类型', dataIndex: 'alert_type', render: (v: string) => alertTypeLabel(v) },
    { title: '级别', dataIndex: 'severity',
      render: (v: string) => <Tag color={severityColor(v)}>{severityLabel(v)}</Tag> },
    { title: '消息', dataIndex: 'message', ellipsis: true },
    { title: '时间', dataIndex: 'fired_at', render: (v: string) => v?.slice(0, 16).replace('T', ' ') },
  ]

  return (
    <div>
      <Row gutter={[16, 16]}>
        {statsCards.map(c => (
          <Col key={c.title} xs={24} sm={12} md={6}>
            <Card hoverable onClick={() => nav(c.route)} style={{ cursor: 'pointer' }}>
              <Statistic title={c.title} value={c.value}
                valueStyle={{ color: c.color, fontSize: 28 }} />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="前沿技术 Top 5（融合评分）" size="small">
            {frontier.isLoading ? <Spin /> :
             frontier.isError ? <Alert type="error" message="加载失败" /> :
             <Table
               dataSource={frontier.data?.items}
               columns={frontierCols}
               rowKey="id"
               size="small"
               pagination={false}
               onRow={() => ({ onClick: () => nav('/scan'), style: { cursor: 'pointer' } })}
             />}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="最新告警" size="small">
            {alerts.isLoading ? <Spin /> :
             alerts.isError ? <Alert type="error" message="加载失败" /> :
             <Table
               dataSource={alerts.data?.items}
               columns={alertCols}
               rowKey="id"
               size="small"
               pagination={false}
               onRow={() => ({ onClick: () => nav('/scan'), style: { cursor: 'pointer' } })}
             />}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
