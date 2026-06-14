// 备考软文图片生成工具类型

/** 卡片类型 */
export type CardType =
  | 'cover'
  | 'plan'
  | 'subjects'
  | 'notice'
  | 'cta'
  | 'resources'
  | 'priority'
  | 'mnemonics'
  | 'study_material'

export const CardTypeMeta: Record<CardType, { label: string; badge: string }> = {
  cover: { label: '📔 封面', badge: 'badge-cover' },
  plan: { label: '📅 学习计划', badge: 'badge-plan' },
  subjects: { label: '📚 考试科目', badge: 'badge-subjects' },
  notice: { label: '⚠️ 考前须知', badge: 'badge-notice' },
  cta: { label: '💬 行动引导', badge: 'badge-cta' },
  resources: { label: '📦 备考资料', badge: 'badge-resources' },
  priority: { label: '📊 分值分布', badge: 'badge-priority' },
  mnemonics: { label: '🧠 记忆口诀', badge: 'badge-mnemonics' },
  study_material: { label: '📖 学习资料', badge: 'badge-study-material' },
}

/** 学习日程中的一天 */
export interface PlanDay {
  date: string   // "M.D"
  weekday: string // "周一"
  task: string
  duration: string
  phaseBreak?: 'start' | 'end'  // 可选：标识阶段分隔点
}

/** 学习资料卡片中的知识模块 */
export interface StudyMaterialItem {
  module_title: string
  key_points: string[]
  memory_tips: string[]
  source?: 'knowledge_base' | 'llm_search'
}

/** 条目（科目/注意事项） */
export interface CardItem {
  label: string
  content: string
}

/** 单张卡片数据 */
export interface CardData {
  type: CardType
  title: string
  subtitle: string
  days: PlanDay[]
  items: CardItem[]
  qrcode_url: string
  study_material?: StudyMaterialItem[]
  /** V3.2 plan 卡片专属:过来人心得(2-3句口语化备考经验) */
  mentor_note?: string
}

/** AI 生成的完整内容 */
export interface GeneratedContent {
  cards: CardData[]
}

/** 文本审核修改记录 */
export interface ReviewModification {
  type: 'sensitive' | 'duplicate' | 'manual_edit'
  typeLabel: string
  feedback: string
  cardIndex: number
  cardType: CardType
  original: CardData
  modified: CardData
  time: string
}

/** 风格 Token */
export interface StyleToken {
  key: string
  name: string
  cssVars: Record<string, string>
}

/** 导出格式 */
export type ExportFormat = 'png_all' | 'png_single' | 'layered'

/** 考试预设 */
export interface ExamPreset {
  name: string
  examDate: string
  subjects: string[]
}

/** 角色 */
export interface Role {
  name: string
  label: string
}

/** 进度步骤 */
export interface ProgressStep {
  id: number
  label: string
  status: 'pending' | 'current' | 'done'
}

/** Dify Workflow 输入参数 */
export interface DifyGenerateParams {
  examName: string
  examDate: string
  cardSequence: CardType[]
  role: string
  countdownDays?: number    // 距离考试天数，前端精确计算
  phase1End?: string        // 基础阶段结束日期 YYYY-MM-DD
  phase2End?: string        // 强化阶段结束日期 YYYY-MM-DD
  targetAudience?: string   // V1.1 目标人群标签或自定义文本
  theme?: string            // V1.1 主题方向预设名或自定义文本
  includeStudyMaterial?: boolean  // V1.1 是否包含学习资料卡片
  chapterIndex?: string     // V3 知识库章节索引 JSON，仅匹配的考试传入
}

/** Dify Workflow 输出（预期结构，后续根据实际情况调整） */
export type DifyGenerateResult = GeneratedContent
