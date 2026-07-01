import { apiFetch } from './httpClient'

export type XhsSourceMode = 'database' | 'custom_text'
export type XhsAngleType = '错因诊断' | '口诀记忆' | '避坑纠偏' | '阶段补救'
export type XhsCtaType = '收藏+评论卡点' | '收藏复习' | '评论下一篇' | '评论补救'
export type XhsDensity = '短平快' | '信息稍密'

export interface XhsChapterOption {
  chapterId: string
  chapterCode: string
  title: string
  assetCode: string
  assetTitle: string
  assetType: string
  collectionCode: string
  textPreview: string
  textLength: number
}

export interface XhsChaptersResponse {
  items: XhsChapterOption[]
  nextCursor: string | null
}

export interface XhsGeneratePayload {
  source_mode: XhsSourceMode
  chapter_id: string
  custom_text: string
  knowledge_keyword: string
  angle_type: XhsAngleType
  target_user: string
  tone: string
  density: XhsDensity
  cta_type: XhsCtaType
  extra_requirement: string
}

export interface XhsTitleCandidate {
  index: number
  title: string
  style: string
}

export interface XhsGeneratedCard {
  card_no: number
  title: string
  body: string
  layout_hint: string
}

export interface XhsGeneratedData {
  meta: {
    angle_type: string
    target_user: string
    tone: string
    length_style: string
    cta_type: string
  }
  internal: {
    source_basis: Array<{ source: string; quote: string }>
    core_point: string
    risk_notes: string[]
    self_check: string[]
  }
  external: {
    title_candidates: XhsTitleCandidate[]
    selected_title_index: number
    cover_copy: string
    cards: XhsGeneratedCard[]
    caption: string
    hashtags: string[]
    cta: string
    today_action: string
  }
  next_topics: Array<{ title: string; angle_type: string; reason: string }>
}

export interface XhsGenerateResponse {
  ok: boolean
  data: XhsGeneratedData | null
  raw_output: string
  error: { code: string; message: string } | null
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value))
  })
  const query = search.toString()
  return query ? `?${query}` : ''
}

export function fetchXhsChapters(params: {
  certificateCode?: string
  query?: string
  limit?: number
} = {}): Promise<XhsChaptersResponse> {
  return apiFetch<XhsChaptersResponse>(`/api/xhs-content/chapters${buildQuery({
    certificate_code: params.certificateCode,
    query: params.query,
    limit: params.limit ?? 80,
  })}`)
}

export function generateXhsContent(payload: XhsGeneratePayload): Promise<XhsGenerateResponse> {
  return apiFetch<XhsGenerateResponse>('/api/xhs-content/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
