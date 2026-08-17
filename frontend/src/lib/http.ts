import { env } from '@/lib/env'
import { supabase } from '@/lib/supabase'

const DEFAULT_TIMEOUT_MS = 15_000

export class ApiError extends Error {
  /** HTTP status code, or `null` when the request never reached the server. */
  status: number | null
  /** True for network/CORS/timeout failures, as opposed to an HTTP error response. */
  isNetworkError: boolean

  constructor(message: string, status: number | null, isNetworkError: boolean) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.isNetworkError = isNetworkError
  }
}

export type RequestOptions = {
  method?: string
  body?: unknown
  signal?: AbortSignal
  timeoutMs?: number
}

export async function authHeader(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession()
  return session ? { Authorization: `Bearer ${session.access_token}` } : {}
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, timeoutMs = DEFAULT_TIMEOUT_MS } = options

  const timeoutController = new AbortController()
  const timeout = setTimeout(() => timeoutController.abort(), timeoutMs)
  signal?.addEventListener('abort', () => timeoutController.abort())

  let response: Response
  try {
    response = await fetch(`${env.apiBaseUrl}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(await authHeader()),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: timeoutController.signal,
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Network request failed'
    throw new ApiError(message, null, true)
  } finally {
    clearTimeout(timeout)
  }

  if (!response.ok) {
    const errorBody: unknown = await response.json().catch(() => null)
    const detail =
      errorBody &&
      typeof errorBody === 'object' &&
      'detail' in errorBody &&
      typeof errorBody.detail === 'string'
        ? errorBody.detail
        : `Request failed with status ${response.status}`
    throw new ApiError(detail, response.status, false)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
