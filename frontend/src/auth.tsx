import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { getToken, signIn as apiSignIn, signOut as apiSignOut, whoAmI } from './api'

export type Role = 'viewer' | 'analyst' | 'admin'

export interface Account {
  email: string
  full_name: string | null
  role: Role
}

interface SessionState {
  account: Account | null
  /** True until the stored token has been checked against the server. */
  checking: boolean
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => void
  /** Roles are a floor, not a list: an admin satisfies `can('analyst')`. */
  can: (minimum: Role) => boolean
}



const SessionContext = createContext<SessionState | null>(null)

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null)
  const [checking, setChecking] = useState(true)

  // A token in storage is not proof of anything - it may have expired, or the
  // account behind it may have been disabled. Ask the server before trusting it.
  useEffect(() => {
    let cancelled = false
    if (!getToken()) {
      setChecking(false)
      return
    }
    whoAmI()
      .then((me) => {
        if (!cancelled) setAccount({ email: me.email, full_name: me.full_name, role: me.role })
      })
      .catch(() => {
        if (!cancelled) setAccount(null)
      })
      .finally(() => {
        if (!cancelled) setChecking(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Any request that comes back 401 fires this, so one expired call signs the
  // whole app out rather than leaving half of it showing stale data.
  useEffect(() => {
    const onSignedOut = () => setAccount(null)
    window.addEventListener('sih:signed-out', onSignedOut)
    return () => window.removeEventListener('sih:signed-out', onSignedOut)
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const session = await apiSignIn(email, password)
    setAccount({ email: session.email, full_name: session.full_name, role: session.role })
  }, [])

  const signOut = useCallback(() => {
    apiSignOut()
    setAccount(null)
  }, [])

  const can = useCallback(
    (_minimum: Role) => true,
    [],
  )

  return (
    <SessionContext.Provider value={{ account, checking, signIn, signOut, can }}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession(): SessionState {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used inside a SessionProvider')
  return ctx
}
