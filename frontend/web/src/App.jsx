import { useState, useEffect, useCallback } from 'react'
import Chat from './components/Chat'
import Sidebar from './components/Sidebar'
import StarField from './components/StarField'
import SocView from './components/SocView'
import OffensiveView from './components/OffensiveView'
import CodeView from './components/CodeView'
import KnowledgeView from './components/KnowledgeView'
import LifeView from './components/LifeView'
import VisionView from './components/VisionView'
import AutonomyView from './components/AutonomyView'
import MemoryView from './components/MemoryView'
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
  const [view,  setView]  = useState('chat')
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
      <div className="app">
        <Sidebar
          view={view} onNav={setView}
          theme={theme} onTheme={setTheme}
          onNewChat={handleNewChat}
          alertCount={alertCount}
        />
        <main className="main">
          {view === 'chat'      && <Chat sessionId={sessionId} onNewChat={handleNewChat} />}
          {view === 'soc'       && <SocView />}
          {view === 'offensive' && <OffensiveView />}
          {view === 'memory'    && <MemoryView key="memory" />}
          {view === 'code'      && <CodeView />}
          {view === 'knowledge' && <KnowledgeView />}
          {view === 'life'      && <LifeView />}
          {view === 'vision'    && <VisionView />}
          {view === 'autonomy'  && <AutonomyView onUnreadChange={setAlertCount} />}
        </main>
      </div>
    </>
  )
}
