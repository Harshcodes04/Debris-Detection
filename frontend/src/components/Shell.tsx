import { AlertTriangle, Radar, Inbox } from 'lucide-react'

export function Wrap({ children, wide }: { children: React.ReactNode; wide?: boolean }) {
  return (
    <div className={`mx-auto ${wide ? 'max-w-7xl' : 'max-w-5xl'} px-4 sm:px-6 py-6 sm:py-8`}>
      {children}
    </div>
  )
}

export function Loading({ what }: { what: string }) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-wreck/30 bg-panel/70 px-5 py-4 text-sm shadow-none">
      <div className="relative flex h-5 w-5 items-center justify-center">
        <Radar className="h-5 w-5 animate-spin text-wreck" />
      </div>
      <span className="font-mono text-slate-200">{what}</span>
    </div>
  )
}

export function Failed({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error)
  return (
    <div className="rounded-md border border-ghost/40 bg-ghost/10 p-5 text-sm text-rose-300 bg-clip-padding">
      <div className="flex items-center gap-2 font-semibold text-rose-200">
        <AlertTriangle className="h-5 w-5 text-ghost" />
        Backend Connection Notice
      </div>
      <div className="mt-2 font-mono text-xs text-rose-300/90 bg-rose-950/40 p-2.5 rounded border border-ghost/20">
        {msg}
      </div>
      <div className="mt-3 text-xs text-rose-300/70">
        Note: The platform is running with fallback intelligence data for demonstration. Connect FastAPI backend on port 8000 for live stream inference.
      </div>
    </div>
  )
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-md border border-line bg-panel/40 p-8 text-center text-muted">
      <Inbox className="h-10 w-10 text-muted/40 mb-2" />
      <div className="text-sm font-medium text-slate-300">{children}</div>
    </div>
  )
}

