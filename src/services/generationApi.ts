import { apiFetch } from '@/services/httpClient'
import type { CardType, DifyGenerateParams, DifyGenerateResult } from '@/types/exam-article'

interface V2GenerationResponse extends DifyGenerateResult {
  runId: number
  status: string
  confidentiality: string
  modelRoute: string
}

function readEnv(key: string): string {
  const env = (typeof process !== 'undefined' ? process.env : {}) as Record<string, string | undefined>
  return env[key] ?? ''
}

function splitEnvList(value: string): string[] {
  return value.split(',').map(item => item.trim()).filter(Boolean)
}

export async function createGeneration(params: DifyGenerateParams): Promise<DifyGenerateResult> {
  const collectionCodes = splitEnvList(readEnv('TARO_APP_GENERATION_COLLECTIONS') || 'coll_internal')
  const knowledgePointCodes = splitEnvList(readEnv('TARO_APP_GENERATION_KNOWLEDGE_POINTS'))

  return apiFetch<V2GenerationResponse>('/api/v2/generations', {
    method: 'POST',
    body: JSON.stringify({
      applicationCode: 'exam_article',
      outputType: 'card_set',
      certificateCode: params.certificateCode,
      collectionCodes,
      knowledgePointCodes,
      cardSequence: params.cardSequence as CardType[],
      inputs: {
        examName: params.examName,
        examDate: params.examDate,
        targetAudience: params.targetAudience ?? '',
        theme: params.theme ?? '',
        role: params.role,
        contentGoal: params.contentGoal ?? 'resource_lead',
        structureTemplate: params.structureTemplate ?? 'resource_lead_v1',
        scriptNodes: params.scriptNodes ?? [],
        leadAssets: params.leadAssets ?? [],
        commentKeyword: params.commentKeyword ?? '',
        conversionModes: params.conversionModes ?? [],
        cardCount: params.cardCount ?? params.cardSequence.length,
        manualBrief: params.manualBrief ?? '',
      },
      idempotencyKey: `exam_article_${Date.now()}`,
    }),
  })
}
