import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, UserPlus } from 'lucide-react'
import * as api from '../api'
import type { Account } from '../api'
import { useSession } from '../auth'
import { Failed, Loading, Wrap } from '../components/Shell'

const ROLES = ['viewer', 'analyst', 'admin'] as const

const WHAT_EACH_ROLE_CAN_DO: Record<string, string> = {
  viewer: 'Read the registry, jobs, detections, reports and the map.',
  analyst: 'Everything a viewer can do, plus uploads, detection runs, day plans and annotation ranking.',
  admin: 'Everything, plus creating and disabling accounts.',
}

export default function Accounts() {
  const { account: me } = useSession()
  const qc = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<string>('viewer')

  const accounts = useQuery({ queryKey: ['accounts'], queryFn: api.listAccounts })

  function run<T>(promise: Promise<T>, message: string) {
    setError(null)
    setNotice(null)
    promise
      .then(() => {
        setNotice(message)
        void qc.invalidateQueries({ queryKey: ['accounts'] })
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'That did not work'))
  }

  const create = useMutation({
    mutationFn: () =>
      api.createAccount({
        email: email.trim(),
        password,
        full_name: fullName.trim() || undefined,
        role,
      }),
    onSuccess: () => {
      setNotice(`Created ${email.trim()}. Tell them the password directly — nothing is emailed.`)
      setError(null)
      setEmail('')
      setFullName('')
      setPassword('')
      setRole('viewer')
      void qc.invalidateQueries({ queryKey: ['accounts'] })
    },
    onError: (e) => setError(e instanceof Error ? e.message : 'Could not create the account'),
  })

  return (
    <Wrap>
      <div className="border-b border-line pb-5">
        <h1 className="text-2xl font-bold tracking-tight text-white">Accounts</h1>
        <p className="mt-1 text-sm text-muted">
          There is no sign-up and no email in this system. Accounts are created here,
          and passwords are handed over directly.
        </p>
      </div>

      {error && <div className="mt-4"><Failed error={new Error(error)} /></div>}
      {notice && (
        <p className="mt-4 rounded border border-safe/40 bg-safe/10 px-3 py-2 text-xs text-safe">
          {notice}
        </p>
      )}

      <section className="mt-6 rounded-md border border-line bg-panel p-5">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
          <UserPlus className="h-4 w-4 text-wreck" />
          New account
        </div>

        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault()
            create.mutate()
          }}
        >
          <div>
            <label className="block text-xs text-muted" htmlFor="new-email">Email</label>
            <input
              id="new-email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="operator@sih.local"
              className="mt-1 w-full rounded border border-line bg-marine-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-wreck"
            />
          </div>

          <div>
            <label className="block text-xs text-muted" htmlFor="new-name">Name (optional)</label>
            <input
              id="new-name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="mt-1 w-full rounded border border-line bg-marine-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-wreck"
            />
          </div>

          <div>
            <label className="block text-xs text-muted" htmlFor="new-password">
              Password (12 characters or more)
            </label>
            <input
              id="new-password"
              type="text"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={12}
              className="mt-1 w-full rounded border border-line bg-marine-950 px-3 py-2 font-mono text-sm text-slate-100 outline-none focus:border-wreck"
            />
            <p className="mt-1 text-[11px] text-[#6e6e75]">
              Shown in clear because you have to read it out — nothing sends it.
            </p>
          </div>

          <div>
            <label className="block text-xs text-muted" htmlFor="new-role">Role</label>
            <select
              id="new-role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="mt-1 w-full rounded border border-line bg-marine-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-wreck"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <p className="mt-1 text-[11px] text-[#6e6e75]">{WHAT_EACH_ROLE_CAN_DO[role]}</p>
          </div>

          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={create.isPending || !email || password.length < 12}
              className="rounded border border-wreck/50 bg-wreck/10 px-4 py-2 text-sm font-medium text-wreck transition-colors hover:bg-wreck/20 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {create.isPending ? 'Creating…' : 'Create account'}
            </button>
          </div>
        </form>
      </section>

      <section className="mt-6">
        {accounts.isLoading && <Loading what="accounts" />}
        {accounts.error && <Failed error={accounts.error} />}

        {accounts.data && (
          <div className="overflow-x-auto rounded-md border border-line">
            <table className="w-full text-left text-xs">
              <thead className="bg-marine-950 font-mono uppercase tracking-wider text-muted">
                <tr>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Last signed in</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {accounts.data.map((a: Account) => {
                  const isMe = a.email === me?.email
                  return (
                    <tr key={a.id} className="hover:bg-marine-900/40">
                      <td className="px-4 py-3 font-mono text-slate-200">
                        {a.email}
                        {isMe && <span className="ml-2 text-[10px] text-[#6e6e75]">(you)</span>}
                      </td>
                      <td className="px-4 py-3 text-slate-300">{a.full_name || '—'}</td>
                      <td className="px-4 py-3">
                        <select
                          value={a.role}
                          disabled={isMe}
                          onChange={(e) =>
                            run(api.setAccountRole(a.id, e.target.value),
                                `${a.email} is now ${e.target.value}`)
                          }
                          className="rounded border border-line bg-marine-950 px-2 py-1 font-mono text-xs text-slate-200 disabled:opacity-50"
                        >
                          {ROLES.map((r) => (
                            <option key={r} value={r}>{r}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        <span className={a.is_active ? 'text-safe' : 'text-[#6e6e75]'}>
                          {a.is_active ? 'active' : 'disabled'}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-[#6e6e75]">
                        {a.last_login_at ? a.last_login_at.slice(0, 16).replace('T', ' ') : 'never'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            title="Set a new password and read it out"
                            onClick={() => {
                              const next = window.prompt(
                                `New password for ${a.email} (12 characters or more).\nNothing is emailed — you will have to tell them.`,
                              )
                              if (!next) return
                              if (next.length < 12) {
                                setError('That password is under 12 characters.')
                                return
                              }
                              run(api.resetAccountPassword(a.id, next),
                                  `Password set for ${a.email}`)
                            }}
                            className="flex items-center gap-1 rounded border border-line px-2 py-1 text-[#8a8a91] hover:border-line-bright hover:text-slate-200"
                          >
                            <KeyRound className="h-3 w-3" /> Reset
                          </button>
                          <button
                            type="button"
                            disabled={isMe}
                            onClick={() =>
                              run(api.setAccountActive(a.id, !a.is_active),
                                  `${a.email} ${a.is_active ? 'disabled' : 'enabled'}`)
                            }
                            className="rounded border border-line px-2 py-1 text-[#8a8a91] hover:border-line-bright hover:text-slate-200 disabled:opacity-40"
                          >
                            {a.is_active ? 'Disable' : 'Enable'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </Wrap>
  )
}
