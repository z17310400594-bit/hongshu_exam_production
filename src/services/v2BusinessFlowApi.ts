import { apiFetch, ApiError } from '@/services/httpClient'
import type {
  V2CertificateDetail,
  V2CertificateExamEventsResponse,
  V2CertificateListResponse,
  V2EligibilityResponse,
  V2GenerationResponse,
  V2KnowledgeSearchResponse,
  V2QuestionBankResponse,
} from '@/types/api'

type ScenarioStatus = 'ok' | 'error'

export interface ScenarioResult<T> {
  status: ScenarioStatus
  data?: T
  error?: {
    status?: number
    code: string
    message: string
    requestId?: string
  }
}

export interface V2BusinessFlowConfig {
  certificateCode: string
  gapCertificateCode: string
  paperCode: string
  collectionCode: string
  restrictedOrgCode: string
  knowledgeQuery: string
  asOf: string
}

export interface V2BusinessFlowSnapshot {
  config: V2BusinessFlowConfig
  certificateList: ScenarioResult<V2CertificateListResponse>
  certificateDetail: ScenarioResult<V2CertificateDetail>
  examEvents: ScenarioResult<V2CertificateExamEventsResponse>
  eligibility: ScenarioResult<V2EligibilityResponse>
  knowledgeSearch: ScenarioResult<V2KnowledgeSearchResponse>
  restrictedKnowledgeSearch: ScenarioResult<V2KnowledgeSearchResponse>
  questionBank: ScenarioResult<V2QuestionBankResponse>
  gapEligibility: ScenarioResult<V2EligibilityResponse>
}

function readEnv(key: string): string {
  const env = (typeof process !== 'undefined' ? process.env : {}) as Record<string, string | undefined>
  return env[key] ?? ''
}

function envOr(key: string, fallback: string): string {
  return readEnv(key) || fallback
}

export function isV2BusinessFlowEnabled(): boolean {
  return readEnv('TARO_APP_SHOW_V2_FLOW') !== 'false'
}

export function getV2BusinessFlowConfig(): V2BusinessFlowConfig {
  return {
    certificateCode: envOr('TARO_APP_V2_FLOW_CERTIFICATE_CODE', 'pharmacist_licensed'),
    gapCertificateCode: envOr('TARO_APP_V2_FLOW_GAP_CERTIFICATE_CODE', 'cls1_constructor'),
    paperCode: envOr('TARO_APP_V2_FLOW_PAPER_CODE', 'P2_PHARMACIST_YAO1_SAMPLE'),
    collectionCode: envOr('TARO_APP_V2_FLOW_COLLECTION_CODE', 'coll_internal'),
    restrictedOrgCode: envOr('TARO_APP_V2_FLOW_RESTRICTED_ORG_CODE', 'org_operations'),
    knowledgeQuery: envOr('TARO_APP_V2_FLOW_KNOWLEDGE_QUERY', 'AUC'),
    asOf: envOr('TARO_APP_V2_FLOW_AS_OF', '2026-06-30'),
  }
}

function toScenarioError(error: unknown): ScenarioResult<never>['error'] {
  if (error instanceof ApiError) {
    return {
      status: error.status,
      code: error.code,
      message: error.message,
      requestId: error.requestId,
    }
  }
  if (error instanceof Error) {
    return {
      code: 'CLIENT_ERROR',
      message: error.message,
    }
  }
  return {
    code: 'UNKNOWN_ERROR',
    message: '未知错误',
  }
}

async function capture<T>(request: Promise<T>): Promise<ScenarioResult<T>> {
  try {
    return { status: 'ok', data: await request }
  } catch (error) {
    return { status: 'error', error: toScenarioError(error) }
  }
}

function eligibilityPayload(certificateCode: string, config: V2BusinessFlowConfig) {
  return {
    certificateCode,
    asOf: config.asOf,
    degreeLevelCode: 'bachelor',
    majorCategoryCode: certificateCode === config.certificateCode ? 'pharmacy' : 'related',
    educationTypeCode: 'full_time',
    totalWorkMonths: certificateCode === config.certificateCode ? 24 : 48,
    relevantWorkMonths: certificateCode === config.certificateCode ? 24 : 36,
  }
}

export async function fetchV2BusinessFlowSnapshot(): Promise<V2BusinessFlowSnapshot> {
  const config = getV2BusinessFlowConfig()
  const certificatePath = `/api/v2/certificates/${encodeURIComponent(config.certificateCode)}`
  const examPath = `${certificatePath}/exam-events?exam_year=2026`

  const [
    certificateList,
    certificateDetail,
    examEvents,
    eligibility,
    knowledgeSearch,
    restrictedKnowledgeSearch,
    questionBank,
    gapEligibility,
  ] = await Promise.all([
    capture(apiFetch<V2CertificateListResponse>('/api/v2/certificates?limit=5')),
    capture(apiFetch<V2CertificateDetail>(certificatePath)),
    capture(apiFetch<V2CertificateExamEventsResponse>(examPath)),
    capture(apiFetch<V2EligibilityResponse>('/api/v2/eligibility/evaluate', {
      method: 'POST',
      body: JSON.stringify(eligibilityPayload(config.certificateCode, config)),
    })),
    capture(apiFetch<V2KnowledgeSearchResponse>('/api/v2/knowledge/search', {
      method: 'POST',
      body: JSON.stringify({
        query: config.knowledgeQuery,
        collectionCodes: [config.collectionCode],
        topK: 5,
      }),
    })),
    capture(apiFetch<V2KnowledgeSearchResponse>('/api/v2/knowledge/search', {
      method: 'POST',
      headers: { 'X-Org-Code': config.restrictedOrgCode },
      body: JSON.stringify({
        query: config.knowledgeQuery,
        collectionCodes: [config.collectionCode],
        topK: 5,
      }),
    })),
    capture(apiFetch<V2QuestionBankResponse>(`/papers/${encodeURIComponent(config.paperCode)}/questions`)),
    capture(apiFetch<V2EligibilityResponse>('/api/v2/eligibility/evaluate', {
      method: 'POST',
      body: JSON.stringify(eligibilityPayload(config.gapCertificateCode, config)),
    })),
  ])

  return {
    config,
    certificateList,
    certificateDetail,
    examEvents,
    eligibility,
    knowledgeSearch,
    restrictedKnowledgeSearch,
    questionBank,
    gapEligibility,
  }
}

export async function createV2BusinessFlowGeneration(): Promise<V2GenerationResponse> {
  const config = getV2BusinessFlowConfig()
  return apiFetch<V2GenerationResponse>('/api/v2/generations', {
    method: 'POST',
    body: JSON.stringify({
      applicationCode: 'exam_article',
      outputType: 'card_set',
      certificateCode: config.certificateCode,
      collectionCodes: [config.collectionCode],
      cardSequence: ['countdown', 'knowledge', 'tips'],
      inputs: {
        examName: '执业药师职业资格考试',
        examDate: '2026-10-31',
        targetAudience: '教材与教辅研发同事',
        theme: '药学专业知识（一）AUC 高频考点',
        role: 'teaching_materials',
      },
      idempotencyKey: `v2_flow_${Date.now()}`,
    }),
  })
}
