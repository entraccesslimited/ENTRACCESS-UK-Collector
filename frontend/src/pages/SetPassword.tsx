import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { Alert } from '@/components/ui'
import { api } from '@/lib/api'
import { landingFor, useSession } from '@/lib/session'

interface LinkInfo {
  full_name: string
  email: string
  first_time: boolean
}

/**
 * Where somebody chooses a password from an emailed link: an invitation to a
 * new account, or a reset. The link is checked before anything is typed, so a
 * dead one says so at once rather than after the form is filled in.
 */
export function SetPassword() {
  const { setPassword } = useSession()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [info, setInfo] = useState<LinkInfo | null>(null)
  const [linkError, setLinkError] = useState<string | null>(token ? null : 'This link is incomplete.')
  const [password, setPasswordValue] = useState('')
  const [repeat, setRepeat] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!token) return
    api<LinkInfo>(`/auth/set-password?token=${encodeURIComponent(token)}`)
      .then(setInfo)
      .catch((err: unknown) =>
        setLinkError(err instanceof Error ? err.message : 'That link cannot be used.'),
      )
  }, [token])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (password !== repeat) {
      setError('The two passwords do not match.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const user = await setPassword(token, password)
      navigate(landingFor(user, null), { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save that password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink p-4">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4" noValidate>
        <div className="flex items-center gap-3">
          <img src="/favicon.svg" alt="" className="size-10 rounded-lg" />
          <div>
            <h1 className="text-lg font-bold">
              {info && !info.first_time ? 'Choose a new password' : 'Set up your account'}
            </h1>
            <p className="text-sm text-slate-500">ENTRACCESS UK Collector</p>
          </div>
        </div>

        {linkError ? (
          <>
            <Alert>{linkError}</Alert>
            <p className="text-sm text-slate-600">
              Ask for a new link from{' '}
              <Link to="/sign-in?forgot=1" className="text-brand-700 underline">
                Forgot your password?
              </Link>{' '}
              on the sign-in page, or ask your nursery to send the invitation again.
            </p>
          </>
        ) : !info ? (
          <p className="text-sm text-slate-500">Checking your link…</p>
        ) : (
          <>
            <p className="text-sm text-slate-600">
              Hello {info.full_name}. Choose a password for <strong>{info.email}</strong>. Nobody
              else will know it.
            </p>
            {error && <Alert>{error}</Alert>}
            <input type="email" autoComplete="username" value={info.email} readOnly hidden />
            <label className="block">
              <span className="label">New password</span>
              <input
                className="input"
                type="password"
                autoComplete="new-password"
                minLength={10}
                value={password}
                onChange={(e) => setPasswordValue(e.target.value)}
                required
              />
              <span className="mt-1 block text-xs text-slate-500">At least 10 characters.</span>
            </label>
            <label className="block">
              <span className="label">Repeat it</span>
              <input
                className="input"
                type="password"
                autoComplete="new-password"
                value={repeat}
                onChange={(e) => setRepeat(e.target.value)}
                required
              />
            </label>
            <button
              className="btn btn-primary w-full"
              disabled={busy || password.length < 10 || !repeat}
            >
              {busy ? 'Saving…' : 'Save and sign in'}
            </button>
          </>
        )}
      </form>
    </div>
  )
}
