import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'

import { Alert } from '@/components/ui'
import { api } from '@/lib/api'
import { landingFor, PORTALS, useSession, type PortalKey } from '@/lib/session'

export function SignIn() {
  const { me, signIn } = useSession()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const portalKey = params.get('portal') as PortalKey | null
  const portal = portalKey && portalKey in PORTALS ? PORTALS[portalKey] : null
  const next = params.get('next') ?? portal?.path ?? null
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // Asking for a link instead of signing in. Reached from the button below,
  // or from a dead set-password link via ?forgot=1.
  const [forgot, setForgot] = useState(params.get('forgot') === '1')
  const [sent, setSent] = useState<string | null>(null)

  if (me) return <Navigate to={landingFor(me, next)} replace />

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const user = await signIn(email, password)
      navigate(landingFor(user, next), { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not sign in.')
    } finally {
      setBusy(false)
    }
  }

  const requestLink = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const answer = await api<{ message: string }>('/auth/forgot-password', {
        method: 'POST',
        json: { email },
      })
      setSent(answer.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send a link just now.')
    } finally {
      setBusy(false)
    }
  }

  if (forgot) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink p-4">
        <form onSubmit={requestLink} className="card w-full max-w-sm space-y-4" noValidate>
          <div className="flex items-center gap-3">
            <img src="/favicon.svg" alt="" className="size-10 rounded-lg" />
            <div>
              <h1 className="text-lg font-bold">Forgot your password?</h1>
              <p className="text-sm text-slate-500">We will email you a link to choose a new one.</p>
            </div>
          </div>
          {error && <Alert>{error}</Alert>}
          {sent ? (
            <p className="text-sm text-slate-600">
              {sent} It lasts an hour. Check your spam folder if it has not arrived in a few
              minutes.
            </p>
          ) : (
            <>
              <label className="block">
                <span className="label">Email</span>
                <input className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </label>
              <button className="btn btn-primary w-full" disabled={busy || !email}>
                {busy ? 'Sending…' : 'Email me a link'}
              </button>
            </>
          )}
          <button
            type="button"
            className="text-sm text-brand-700 underline"
            onClick={() => {
              setForgot(false)
              setSent(null)
              setError(null)
            }}
          >
            Back to sign in
          </button>
        </form>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink p-4">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4" noValidate>
        <div className="flex items-center gap-3">
          <img src="/favicon.svg" alt="" className="size-10 rounded-lg" />
          <div>
            <h1 className="text-lg font-bold">{portal ? portal.title : 'ENTRACCESS UK'}</h1>
            <p className="text-sm text-slate-500">Every handover, authorised.</p>
          </div>
        </div>
        {error && <Alert>{error}</Alert>}
        <label className="block">
          <span className="label">Email</span>
          <input className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label className="block">
          <span className="label">Password</span>
          <input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        <button className="btn btn-primary w-full" disabled={busy || !email || !password}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
        <button
          type="button"
          className="text-sm text-brand-700 underline"
          onClick={() => {
            setForgot(true)
            setError(null)
          }}
        >
          Forgot your password?
        </button>
        <p className="text-xs text-slate-500">
          Parents, room leaders, managers and ENTRACCESS UK all sign in here.{' '}
          <Link to="/portals" className="text-brand-700 underline">
            Choose a portal
          </Link>
        </p>
      </form>
    </div>
  )
}
