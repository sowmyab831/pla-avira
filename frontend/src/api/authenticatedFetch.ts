import { config } from '../config'

/**
 * Preserve native fetch/FormData semantics while authenticating private routes.
 * Equivalent to fetch() with Authorization injected; kept for explicit call sites.
 */
export function authenticatedFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers)
  const token = localStorage.getItem('auth_token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  return fetch(input, { ...init, headers })
}

let _installed = false

/**
 * Wrap window.fetch once so EVERY call to the PLA API carries the Bearer
 * token — including pages that still use plain fetch(). A 401 with a token
 * present means the session expired: clear auth state and bounce to login.
 */
export function installAuthFetch() {
  if (_installed || typeof window === 'undefined' || !window.fetch) return
  _installed = true
  const original = window.fetch.bind(window)
  window.fetch = async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    const isApi = url.startsWith(config.apiBase) || url.startsWith('/api/')
    if (!isApi) return original(input, init)

    const headers = new Headers(init.headers ?? (input instanceof Request ? input.headers : undefined))
    const token = localStorage.getItem('auth_token')
    if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)

    const resp = await original(input, { ...init, headers })
    if (resp.status === 401 && token) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_user')
      if (window.location.pathname !== '/') window.location.assign('/')
      else window.location.reload()
    }
    return resp
  }
}
