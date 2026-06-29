import { apiFetch } from '@/services/httpClient'
import type {
  V2CertificateExamEventsResponse,
  V2CertificateListResponse,
  V2CertificateSummary,
  V2ExamEvent,
  V2ExamPhase,
} from '@/types/api'

function readEnv(key: string): string {
  const env = (typeof process !== 'undefined' ? process.env : {}) as Record<string, string | undefined>
  return env[key] ?? ''
}

export function useV2CertificateApi(): boolean {
  return readEnv('TARO_APP_USE_V2_CERTIFICATE_API') !== 'false'
}

export function pickExamDateFromPhases(phases: V2ExamPhase[] = []): string {
  const written = phases.find(phase => (phase.type ?? phase.phaseType) === 'written')
  return written?.startsOn ?? phases[0]?.startsOn ?? ''
}

export function pickExamDateFromEvent(event: V2ExamEvent | null | undefined): string {
  return event ? pickExamDateFromPhases(event.phases) : ''
}

export function pickExamDateFromCertificate(cert: V2CertificateSummary): string {
  return pickExamDateFromPhases(cert.nextExam?.phases ?? [])
}

export async function fetchV2Certificates(query = '', limit = 50): Promise<V2CertificateListResponse> {
  const params = new URLSearchParams()
  if (query) params.set('query', query)
  params.set('limit', String(limit))
  return apiFetch<V2CertificateListResponse>(`/api/v2/certificates?${params.toString()}`)
}

export async function fetchV2CertificateExamEvents(certificateCode: string): Promise<V2CertificateExamEventsResponse> {
  return apiFetch<V2CertificateExamEventsResponse>(`/api/v2/certificates/${encodeURIComponent(certificateCode)}/exam-events`)
}

export async function fetchV2CertificateExamDate(certificateCode: string): Promise<string> {
  const result = await fetchV2CertificateExamEvents(certificateCode)
  return pickExamDateFromEvent(result.selectedEvent)
}
