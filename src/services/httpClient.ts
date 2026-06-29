import type { ApiErrorBody, ApiFieldError } from '@/types/api'

function readEnv(key: string): string {
  const env = (typeof process !== 'undefined' ? process.env : {}) as Record<string, string | undefined>
  return env[key] ?? ''
}

function defaultApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    return `http://${window.location.hostname}:8000`
  }
  return 'http://localhost:8000'
}

export const API_BASE_URL = readEnv('TARO_APP_API_BASE_URL') || defaultApiBaseUrl()
export const ORG_CODE = readEnv('TARO_APP_ORG_CODE') || 'org_teaching_materials'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string
  readonly fieldErrors: ApiFieldError[]

  private constructor(status: number, code: string, message: string, requestId: string, fieldErrors: ApiFieldError[]) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
    this.fieldErrors = fieldErrors
  }

  static async fromResponse(response: Response): Promise<ApiError> {
    const requestId = response.headers.get('X-Request-ID') ?? ''
    let body: ApiErrorBody = {}
    try {
      body = await response.json() as ApiErrorBody
    } catch {
      // Non-JSON error body; keep stable fallback below.
    }
    const error = body.error
    return new ApiError(
      response.status,
      error?.code ?? `HTTP_${response.status}`,
      error?.message ?? `API 请求失败 (${response.status})`,
      error?.requestId ?? requestId,
      error?.fieldErrors ?? [],
    )
  }
}

function buildRequestId(): string {
  return `req_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', headers.get('Content-Type') ?? 'application/json')
  headers.set('X-Request-ID', headers.get('X-Request-ID') ?? buildRequestId())
  headers.set('X-Org-Code', headers.get('X-Org-Code') ?? ORG_CODE)

  const token = readEnv('TARO_APP_ACCESS_TOKEN')
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  })
  if (!response.ok) throw await ApiError.fromResponse(response)
  return response.json() as Promise<T>
}
