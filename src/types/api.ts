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

export interface V2CertificateDetail extends V2CertificateSummary {
  examAuthority?: string | null
  status?: string
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

export interface V2Citation {
  assetCode?: string
  assetTitle?: string
  fragmentCode?: string
  heading?: string | null
  pageFrom?: number | null
  pageTo?: number | null
  collectionCode?: string
}

export interface V2EligibilityResponse {
  certificateCode: string
  decision: 'eligible' | 'not_eligible' | 'insufficient_data' | string
  reason: string
  dataStatus?: string
  matchedRuleCode?: string | null
  requirements?: Record<string, unknown>
  citations: V2Citation[]
}

export interface V2KnowledgeSearchItem {
  assetCode: string
  assetTitle: string
  assetType: string
  versionNo: number
  fragmentCode: string
  heading?: string | null
  content: string
  pageFrom?: number | null
  pageTo?: number | null
  collectionCode: string
  knowledgePointCodes: string[]
  score: number
}

export interface V2KnowledgeSearchResponse {
  query: string
  items: V2KnowledgeSearchItem[]
  nextCursor: string | null
}

export interface V2QuestionKnowledgePoint {
  code: string
  name: string
  role: string
  scoreWeight?: number | null
}

export interface V2Question {
  questionNo: string
  questionType: string
  content: string
  options: unknown
  answer?: unknown
  analysis?: string | null
  difficulty: number
  sourceFragmentCode?: string | null
  knowledgePoints: V2QuestionKnowledgePoint[]
}

export interface V2QuestionBankResponse {
  status?: string
  paper: {
    code: string
    title: string
    paperType: string
    examYear?: number | null
    certificate: {
      code: string
      name: string
    }
    subject?: {
      code: string
      name: string
    } | null
    ownerOrgCode: string
    sourceAsset: {
      code: string
      title: string
      versionNo: number
    }
  }
  questions: V2Question[]
  stats: {
    questionCount: number
    knowledgePointCount: number
    difficultyDistribution: Record<string, number>
    knowledgePointCoverage: Array<{
      code: string
      name: string
      questionCount: number
      primaryCount: number
    }>
  }
}

export interface V2GenerationResponse {
  runId: number
  status: string
  applicationCode: string
  outputType?: string | null
  confidentiality: string
  modelRoute: string
  cards: Array<{
    id?: string
    title?: string
    subtitle?: string
    body?: string
  }>
  citations: V2Citation[]
  createdAt: string
}
