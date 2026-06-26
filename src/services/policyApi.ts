import type { CertsResponse } from '@/types/policy'

const POLICY_API_BASE =
  typeof window !== 'undefined'
    ? `http://${window.location.hostname}:8400`
    : 'http://localhost:8400'

/**
 * Fetch all certificate records from the policy-api database.
 * Throws on non-OK responses; callers handle the error.
 */
export async function fetchCerts(): Promise<CertsResponse> {
  const response = await fetch(`${POLICY_API_BASE}/query/certs`)
  if (!response.ok) {
    throw new Error(`Policy API request failed (${response.status})`)
  }
  return response.json() as Promise<CertsResponse>
}
