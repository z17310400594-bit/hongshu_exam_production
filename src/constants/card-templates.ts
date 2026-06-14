import type { CardType } from '@/types/exam-article'

/** 6 张标准预设 → 升级为含分值分布 + 资料 */
export const PRESET_STANDARD: CardType[] = [
  'cover', 'plan', 'plan', 'priority', 'resources', 'cta',
]

/** 5 张精简预设 → 保持简洁 */
export const PRESET_COMPACT: CardType[] = [
  'cover', 'plan', 'subjects', 'notice', 'cta',
]

/** ★ 新增：计划型（适合备考早期，强调学习计划） */
export const PRESET_PLAN_TYPE: CardType[] = [
  'cover', 'plan', 'plan', 'priority', 'resources', 'cta',
]

/** ★ 新增：知识型（适合备考中期，强调知识点+口诀） */
export const PRESET_KNOWLEDGE_TYPE: CardType[] = [
  'cover', 'subjects', 'priority', 'mnemonics', 'resources', 'cta',
]

/** ★ 新增：工具型（适合所有阶段，强调资料+口诀） */
export const PRESET_TOOL_TYPE: CardType[] = [
  'cover', 'resources', 'mnemonics', 'notice', 'cta',
]

/** V1.1 新增：含备考资料（7 张） */
export const PRESET_WITH_STUDY: CardType[] = [
  'cover', 'plan', 'plan', 'subjects', 'study_material', 'notice', 'cta',
]

/** 所有可用卡片类型 */
export const ALL_CARD_TYPES: CardType[] = [
  'cover', 'plan', 'subjects', 'notice', 'cta',
  'resources', 'priority', 'mnemonics', 'study_material',
]

/** 最少卡片数 */
export const MIN_CARDS = 3

/** 最多卡片数 */
export const MAX_CARDS = 9
