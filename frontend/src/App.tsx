import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Header } from './components/Header'
import Dashboard from './pages/Dashboard'
import Detect from './pages/Detect'
import Hazards from './pages/Hazards'
import HazardDetail from './pages/HazardDetail'
import MapView from './pages/MapView'
import Recovery from './pages/Recovery'
import Annotate from './pages/Annotate'
import About from './pages/About'
import Login from './pages/Login'
import Accounts from './pages/Accounts'
import { useSession } from './auth'

/** The router leaves the scroll where it was, so following a link from a
 *  scrolled page - the map, say - lands you halfway down the next one. */
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export default function App() {
  const { account, checking, can } = useSession()

  // Hold the whole app back until the stored token has been checked, so a
  // signed-in reload does not flash the sign-in form on the way through.
  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0a0b] text-sm text-muted">
        Checking your session…
      </div>
    )
  }

  // One gate for the whole app rather than a guard per route: there is nothing
  // here a signed-out visitor is meant to see.
  if (!account) {
    return (
      <div className="min-h-screen bg-[#0a0a0b] text-slate-100 antialiased font-sans">
        <Login />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0a0a0b] text-slate-100 antialiased font-sans flex flex-col">
      {/* Top Navigation Bar */}
      <ScrollToTop />
      <Header />

      {/* Main Page Area */}
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/detect" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/detect" element={<Detect />} />
          <Route path="/hazards" element={<Hazards />} />
          <Route path="/hazards/:id" element={<HazardDetail />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/recovery" element={<Recovery />} />
          <Route path="/annotate" element={<Annotate />} />
          <Route path="/about" element={<About />} />
          {/* Guarded in the UI as well as the API, so a viewer is not shown a
              page whose every call would come back 403. */}
          <Route
            path="/accounts"
            element={can('admin') ? <Accounts /> : <Navigate to="/detect" replace />}
          />
        </Routes>
      </main>

      {/* Global Marine Intelligence Footer */}
      <footer className="border-t border-[#26262a] bg-[#0c0c0d] px-6 py-4 text-xs font-mono text-[#6e6e75] flex flex-col sm:flex-row sm:justify-between items-center gap-2 max-w-[1600px] mx-auto w-full">
        <div>
          Data: Ghost Pot SSS (PING Ecosystem, CC-BY-SA-4.0) • SCTD • Marine Debris FLS
          <div className="text-[10px] text-[#475569]">
            Smart India Hackathon 2026, Problem Statement 57
          </div>
        </div>
        {/* There is no towfish and no build 4.8.2 - a green dot claiming a
            vessel is online is the kind of thing someone checks. The contract
            version is real and comes from ml/contract.py. */}
        <div className="text-xs text-[#6e6e75]">Contract v1.0.0</div>
      </footer>
    </div>
  )
}
