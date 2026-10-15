/** A thin wrapper over fetch. The session is an HttpOnly cookie, so nothing
 *  here touches a token; every request that changes something carries the
 *  header the API requires, which a cross-site form cannot send. */

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function detail(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const value = (body as { detail: unknown }).detail
    if (typeof value === 'string') return value
    if (Array.isArray(value) && value[0] && typeof value[0] === 'object' && 'msg' in value[0]) {
      return String((value[0] as { msg: unknown }).msg)
    }
  }
  return fallback
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init
  const response = await fetch(`/api${path}`, {
    credentials: 'same-origin',
    ...rest,
    headers: {
      'X-Requested-With': 'fetch',
      ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  })
  if (response.status === 204) return undefined as T
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, detail(body, 'Something went wrong.'))
  return body as T
}
