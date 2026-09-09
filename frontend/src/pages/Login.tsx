import { useState } from 'react'
import { Radio } from 'lucide-react'
import { useSession } from '../auth'
import { registerAccount } from '../api'

export default function Login() {
  const { signIn } = useSession()
  const [isRegistering, setIsRegistering] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (isRegistering) {
        await registerAccount(email.trim(), password, fullName.trim() || undefined)
        await signIn(email.trim(), password)
      } else {
        await signIn(email.trim(), password)
      }
    } catch (err) {
      // The server deliberately does not say which half was wrong for login.
      setError(err instanceof Error ? err.message : `Could not ${isRegistering ? 'register' : 'sign in'}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded border border-line bg-panel text-muted">
            <Radio className="h-4 w-4" />
          </div>
          <div>
            <h1 className="text-base font-bold text-white">Seabed Anomaly Detection</h1>
            <p className="text-[11px] text-[#6e6e75]">Side-scan sonar, ghost gear and wrecks</p>
          </div>
        </div>

        <form onSubmit={submit} className="rounded-md border border-line bg-panel p-6">
          <h2 className="text-sm font-semibold text-slate-200">
            {isRegistering ? 'Create an account' : 'Sign in'}
          </h2>
          <p className="mt-1 text-xs text-muted">
            {isRegistering 
              ? 'Enter your details to register.' 
              : 'Sign in to your account.'}
          </p>

          {isRegistering && (
            <>
              <label className="mt-5 block text-xs text-muted" htmlFor="fullName">
                Full Name (Optional)
              </label>
              <input
                id="fullName"
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="mt-1 w-full rounded border border-line bg-marine-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-wreck"
              />
            </>
          )}

          <label className="mt-4 block text-xs text-muted" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="mt-1 w-full rounded border border-line bg-marine-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-wreck"
          />

          <label className="mt-4 block text-xs text-muted" htmlFor="password">
            Password {isRegistering && '(min 12 characters)'}
          </label>
          <input
            id="password"
            type="password"
            autoComplete={isRegistering ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={isRegistering ? 12 : undefined}
            className="mt-1 w-full rounded border border-line bg-marine-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-wreck"
          />

          {error && (
            <p role="alert" className="mt-4 rounded border border-ghost/40 bg-ghost/10 px-3 py-2 text-xs text-ghost">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy || !email || !password || (isRegistering && password.length < 12)}
            className="mt-5 w-full rounded border border-wreck/50 bg-wreck/10 px-3 py-2 text-sm font-medium text-wreck transition-colors hover:bg-wreck/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? (isRegistering ? 'Registering…' : 'Signing in…') : (isRegistering ? 'Create Account' : 'Sign in')}
          </button>
        </form>

        <p className="mt-4 text-center text-[11px] text-[#6e6e75]">
          {isRegistering ? 'Already have an account? ' : "Don't have an account? "}
          <button 
            type="button" 
            onClick={() => {
              setIsRegistering(!isRegistering)
              setError(null)
            }}
            className="text-wreck hover:underline"
          >
            {isRegistering ? 'Sign in' : 'Create one'}
          </button>
        </p>
        <p className="mt-4 text-center text-[11px] text-[#6e6e75]">
          SIH 2026 · Problem Statement 57
        </p>
      </div>
    </div>
  )
}
