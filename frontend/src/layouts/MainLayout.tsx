import { useState } from 'react'
import { Layout, Menu, Typography, theme } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  DashboardOutlined, ExperimentOutlined, ProjectOutlined,
  BankOutlined, UserOutlined, RadarChartOutlined,
  BulbOutlined, FileTextOutlined,
} from '@ant-design/icons'

const { Sider, Content, Header } = Layout
const { Title } = Typography

const menuItems = [
  { key: 'dashboard',  icon: <DashboardOutlined />,  label: '总览' },
  { key: 'tech',       icon: <ExperimentOutlined />,  label: '技术画像' },
  { key: 'project',    icon: <ProjectOutlined />,     label: '项目画像' },
  { key: 'org',        icon: <BankOutlined />,        label: '机构画像' },
  { key: 'person',     icon: <UserOutlined />,        label: '人员画像' },
  { key: 'scan',       icon: <RadarChartOutlined />,  label: '扫描监测' },
  { key: 'discovery',  icon: <BulbOutlined />,        label: '新技术发现' },
  { key: 'topics',     icon: <FileTextOutlined />,    label: '选题服务' },
]

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { token } = theme.useToken()

  const selected = location.pathname.split('/')[1] || 'dashboard'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}
        style={{ background: token.colorBgContainer, borderRight: `1px solid ${token.colorBorderSecondary}` }}>
        <div style={{ padding: collapsed ? '16px 8px' : '16px 24px', borderBottom: `1px solid ${token.colorBorderSecondary}` }}>
          {!collapsed && (
            <Title level={5} style={{ margin: 0, color: token.colorPrimary }}>MetaProfile</Title>
          )}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selected]}
          items={menuItems}
          onClick={({ key }) => navigate(`/${key}`)}
          style={{ border: 'none', marginTop: 8 }}
        />
      </Sider>
      <Layout>
        <Header style={{
          background: token.colorBgContainer,
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
        }}>
          <Title level={4} style={{ margin: 0 }}>
            {menuItems.find(m => m.key === selected)?.label ?? '产业技术情报系统'}
          </Title>
        </Header>
        <Content style={{ padding: 24, overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
