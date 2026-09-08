import { Navigate, Route, Routes } from 'react-router-dom'
import { Header } from './components/Header'
import Dashboard from './pages/Dashboard'
import Detect from './pages/Detect'
import Hazards from './pages/Hazards'
import MapView from './pages/MapView'
import Recovery from './pages/Recovery'
import Annotate from './pages/Annotate'
import About from './pages/About'

export default function App() {
  return (
    <div className="min-h-screen bg-[#040711] text-slate-100 antialiased font-sans flex flex-col">
      {/* Top Navigation Bar */}
      <Header />

      {/* Main Page Area */}
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/detect" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/detect" element={<Detect />} />
          <Route path="/hazards" element={<Hazards />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/recovery" element={<Recovery />} />
          <Route path="/annotate" element={<Annotate />} />
          <Route path="/about" element={<About />} />
        </Routes>
      </main>

      {/* Global Marine Intelligence Footer */}
      <footer className="border-t border-[#141f36] bg-[#050914] px-6 py-4 text-xs font-mono text-[#64748b] flex flex-col sm:flex-row sm:justify-between items-center gap-2 max-w-[1600px] mx-auto w-full">
        <div>
          Data: Ghost Pot SSS (PING Ecosystem, CC-BY-SA-4.0) • SCTD • Marine Debris FLS
          <div className="text-[10px] text-[#475569]">
            Smart India Hackathon SIH PS57 Marine Track • Dual-Head SSS Autonomous Detection Engine
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="h-2 w-2 rounded-full bg-[#10b981] animate-pulse" />
          <span className="text-slate-300 font-semibold">Towfish Online</span>
          <span className="text-[#475569]">Build 4.8.2-prod</span>
        </div>
      </footer>
    </div>
  )
}
