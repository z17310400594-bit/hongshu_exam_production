export type ApiFieldError = { field?: string; code?: string; message?: string }

/** Shared V2 API DTOs for the Taro frontend. */

export interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
    fieldErrors?: ApiFieldError[]
    requestId?: string
  }
}

export interface V2ExamPhase {
  type?: string
  phaseType?: string
  startsOn: string
  endsOn?: string | null
  note?: string | null
}

export interface V2ExamEvent {
  code: string
  eventCode?: string
  examYear: number
  regionCode: string
  status?: string
  phases: V2ExamPhase[]
}

export interface V2CertificateSummary {
  code: string
  name: string
  categoryCode?: string | null
  issuingAuthority?: string | null
  nationwide?: boolean
  aliases: string[]
  nextExam?: {
    eventCode: string
    examYear: number
    regionCode: string
    phases: V2ExamPhase[]
  } | null
}

export interface V2CertificateListResponse {
  items: V2CertificateSummary[]
  nextCursor: string | null
}

export interface V2CertificateExamEventsResponse {
  certificate: {
    code: string
    name: string
    categoryCode?: string | null
  }
  selectedEvent: V2ExamEvent | null
  events: V2ExamEvent[]
}
