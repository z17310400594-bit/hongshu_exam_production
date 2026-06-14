// 选题分析工具类型

import type { CardType } from '@/types/exam-article'

/** 考试类目 */
export interface ExamCategory {
  id: string
  name: string
  examDate: string // YYYY-MM-DD
  keywords: string[]
  subjects: string[]
  recommendedPreset?: CardType[]  // 推荐卡组（选择考试时自动套用）
}

/** 推荐强度 */
export type Confidence = 'high' | 'medium' | 'low'

export const ConfidenceMeta: Record<Confidence, { text: string; cls: string }> = {
  high: { text: '🔥 强烈推荐', cls: 'high' },
  medium: { text: '⭐ 推荐', cls: 'medium' },
  low: { text: '💡 参考', cls: 'low' },
}

/** 分析依据来源 */
export type ReasonSource = 'internal' | 'phase' | 'external'

export const SourceMeta: Record<ReasonSource, { text: string; cls: string }> = {
  internal: { text: '内部数据', cls: 'internal' },
  phase: { text: '周期规则', cls: 'phase' },
  external: { text: '外部信号', cls: 'external' },
}

/** 单条分析依据 */
export interface AnalysisReason {
  source: ReasonSource
  text: string
}

/** 单条选题 */
export interface Topic {
  rank: number
  title: string
  confidence: Confidence
  reasons: AnalysisReason[]
}

/** 选题分析结果 */
export interface TopicAnalysisResult {
  categoryId: string
  categoryName: string
  examDate: string
  daysRemaining: number
  currentPhase: string
  generatedAt: string
  dataSource: {
    historyCount: number
    phaseRulesUsed: boolean
  }
  topics: Topic[]
}

/** 考试周期阶段 */
export type PhaseName = '备考早期' | '备考中期' | '冲刺期' | '考前' | '考后'

/** 周期规则中的选题类型推荐 */
export interface PhaseTopicType {
  type: string
  reason: string
}

/** 周期规则定义 */
export interface PhaseRule {
  phase: PhaseName
  daysRange: [number, number] // [min, max]，max 为 999 表示无上限
  recommendedTypes: PhaseTopicType[]
}

/** 历史选题记录（MD 解析后） */
export interface HistoryRecord {
  id: string
  categoryId: string
  topic: string
  noteType: string
  account: string
  pubDate: string
  daysBeforeExam: number
  likes: number
  saves: number
  comments: number
  notes: string
}

/** 历史数据导入状态 */
export interface HistoryDataState {
  records: HistoryRecord[]
  lastUpdate: string
}
