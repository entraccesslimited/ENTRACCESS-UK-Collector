import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

import { api, ApiError } from './api'
import type { Me } from './types'

interface SessionState {
  me: Me | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<Me>
  signOut: () => Promise<void>
}

const SessionContext = createContext<SessionState | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api<Me>('/auth/me')
      .then(setMe)
      .catch((error: unknown) => {
        if (!(error instanceof ApiError && error.status === 401)) console.error(error)
      })
      .finally(() => setLoading(false))
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const user = await api<Me>('/auth/sign-in', { method: 'POST', json: { email, password } })
    setMe(user)
    return user
  }, [])

  const signOut = useCallback(async () => {
    await api('/auth/sign-out', { method: 'POST' }).catch(() => undefined)
    setMe(null)
  }, [])

  return (
    <SessionContext.Provider value={{ me, loading, signIn, signOut }}>{children}</SessionContext.Provider>
  )
}

export function useSession(): SessionState {
  const value = useContext(SessionContext)
  if (!value) throw new Error('useSession outside SessionProvider')
  return value
}

export function homeFor(me: Me): string {
  return { parent: '/parent', staff: '/door', admin: '/admin', operator: '/company' }[me.role]
}

/** The portals, as somebody arriving chooses between them. */
export const PORTALS = {
  parent: { title: 'Parent portal', path: '/parent', roles: ['parent'] },
  nursery: { title: 'Nursery portal', path: '/admin', roles: ['admin', 'staff'] },
  company: { title: 'Company portal', path: '/company', roles: ['operator'] },
} as const

export type PortalKey = keyof typeof PORTALS

/** Where to go after signing in: the page asked for, if this account may see it. */
export function landingFor(me: Me, next: string | null): string {
  if (!next || !next.startsWith('/') || next.startsWith('//')) return homeFor(me)
  const portal = Object.values(PORTALS).find((p) => next.startsWith(p.path))
  if (portal && !(portal.roles as readonly string[]).includes(me.role)) return homeFor(me)
  if (next.startsWith('/door') && !['staff', 'admin'].includes(me.role)) return homeFor(me)
  return next
}
