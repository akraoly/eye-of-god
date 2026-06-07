import { useState, useEffect, useCallback } from 'react'
import Chat from './components/Chat'
import Sidebar from './components/Sidebar'
import StarField from './components/StarField'
import DashboardView from './components/DashboardView'
import SettingsView from './components/SettingsView'
import { ToastContainer } from './components/NotificationSystem'
import SocView from './components/SocView'
import OffensiveView from './components/OffensiveView'
import CodeView from './components/CodeView'
import KnowledgeView from './components/KnowledgeView'
import LifeView from './components/LifeView'
import VisionView from './components/VisionView'
import AutonomyView from './components/AutonomyView'
import MemoryView from './components/MemoryView'
import ObserveView from './components/ObserveView'
import DiagnosticView from './components/DiagnosticView'
import AegisView from './components/AegisView'
import OsintView from './components/OsintView'
import CredentialsView from './components/CredentialsView'
import ThreatIntelView from './components/ThreatIntelView'
import ForensicsView from './components/ForensicsView'
import PrivEscView from './components/PrivEscView'
import LateralView from './components/LateralView'
import LabView from './components/LabView'
import ReportsView from './components/ReportsView'
import SelfImproveView from './components/SelfImproveView'
import TerminalView from './components/TerminalView'
import AudioCaptureView from './components/AudioCaptureView'
import CameraScanView from './components/CameraScanView'
import PostExploitView from './components/PostExploitView'
import NetworkSnifferView from './components/NetworkSnifferView'
import TriggersView from './components/TriggersView'
import ExfilView from './components/ExfilView'
import OmniscienceView from './components/OmniscienceView'
import SystemMonitorView from './components/SystemMonitorView'
import BLEDashboard from './components/ble/BLEDashboard'
import SDRPanel from './components/sdr/SDRPanel'
import RFIDPanel from './components/rfid/RFIDPanel'
import MitreDashboard from './components/soc/MitreDashboard'
import ReportDashboard from './components/reporting/ReportDashboard'
import RAGDashboard from './components/RAGDashboard'
import UsersManager from './components/admin/UsersManager'
import LoginPage from './pages/Login'
import { auth } from './utils/auth'
import './App.css'

export default function App() {
  const [loggedIn, setLoggedIn] = useState(auth.isLoggedIn())
  if (!loggedIn) return <LoginPage onLogin={() => setLoggedIn(true)} />
  return <MainApp />
}

function MainApp() {
  const [alertCount, setAlertCount] = useState(0)
  const [sessionId, setSessionId] = useState(() => {
    const stored = localStorage.getItem('eye_session_id')
    if (stored) return stored
    const id = crypto.randomUUID()
    localStorage.setItem('eye_session_id', id)
    return id
  })
  const [view,  setView]  = useState('dashboard')
  const [theme, setTheme] = useState('galactic')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const handleNewChat = useCallback(() => {
    const id = crypto.randomUUID()
    localStorage.setItem('eye_session_id', id)
    setSessionId(id)
    setView('chat')
  }, [])

  return (
    <>
      <StarField theme={theme} />
      <ToastContainer />
      <div className="app">
        <Sidebar
          view={view} onNav={setView}
          theme={theme} onTheme={setTheme}
          onNewChat={handleNewChat}
          alertCount={alertCount}
        />
        <main className="main">
          {view === 'dashboard'    && <DashboardView onNav={setView} />}
          {view === 'chat'         && <Chat sessionId={sessionId} onNewChat={handleNewChat} />}
          {view === 'soc'          && <SocView />}
          {view === 'offensive'    && <OffensiveView />}
          {view === 'memory'       && <MemoryView key="memory" />}
          {view === 'code'         && <CodeView />}
          {view === 'knowledge'    && <KnowledgeView />}
          {view === 'life'         && <LifeView />}
          {view === 'vision'       && <VisionView />}
          {view === 'autonomy'     && <AutonomyView onUnreadChange={setAlertCount} />}
          {view === 'observe'      && <ObserveView />}
          {view === 'diagnostic'   && <DiagnosticView />}
          {view === 'aegis'        && <AegisView />}
          {view === 'osint'        && <OsintView />}
          {view === 'credentials'  && <CredentialsView />}
          {view === 'threat-intel' && <ThreatIntelView />}
          {view === 'forensics'    && <ForensicsView />}
          {view === 'privesc'      && <PrivEscView />}
          {view === 'lateral'      && <LateralView />}
          {view === 'lab'          && <LabView />}
          {view === 'reports'      && <ReportsView />}
          {view === 'self-improve' && <SelfImproveView />}
          {view === 'terminal'     && <TerminalView />}
          {view === 'audio'        && <AudioCaptureView />}
          {view === 'cameras'      && <CameraScanView />}
          {view === 'post-exploit' && <PostExploitView />}
          {view === 'sniffer'      && <NetworkSnifferView />}
          {view === 'triggers'     && <TriggersView />}
          {view === 'exfil'        && <ExfilView />}
          {view === 'omniscience'  && <OmniscienceView />}
          {view === 'ble'          && <BLEDashboard />}
          {view === 'sdr'          && <SDRPanel />}
          {view === 'rfid'         && <RFIDPanel />}
          {view === 'mitre'        && <MitreDashboard />}
          {view === 'audit-reports'&& <ReportDashboard />}
          {view === 'sentinel'     && <SystemMonitorView />}
          {view === 'rag'          && <RAGDashboard />}
          {view === 'users'        && <UsersManager />}
          {view === 'settings'     && <SettingsView />}
        </main>
      </div>
    </>
  )
}
