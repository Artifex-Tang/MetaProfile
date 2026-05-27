import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'
import ProfileTech from './pages/ProfileTech'
import ProfileProject from './pages/ProfileProject'
import ProfileOrg from './pages/ProfileOrg'
import ProfilePerson from './pages/ProfilePerson'
import ScanMonitor from './pages/ScanMonitor'
import NewTechDiscovery from './pages/NewTechDiscovery'
import TopicSelection from './pages/TopicSelection'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="tech" element={<ProfileTech />} />
          <Route path="project" element={<ProfileProject />} />
          <Route path="org" element={<ProfileOrg />} />
          <Route path="person" element={<ProfilePerson />} />
          <Route path="scan" element={<ScanMonitor />} />
          <Route path="discovery" element={<NewTechDiscovery />} />
          <Route path="topics" element={<TopicSelection />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
