import type { CardType } from '@/types/exam-article'

/** 卡片类型中英映射：显示用中文，传参用英文 */
export const CARD_TYPE_LABELS: Record<CardType, string> = {
  cover: '封面',
  plan: '学习计划',
  subjects: '考试科目',
  notice: '考前须知',
  cta: '行动引导',
  resources: '备考资料',
  priority: '分值分布',
  mnemonics: '记忆口诀',
  study_material: '学习资料',
}

/** 卡片类型 badge 样式映射 */
export const CARD_TYPE_BADGES: Record<CardType, string> = {
  cover: 'badge-cover',
  plan: 'badge-plan',
  subjects: 'badge-subjects',
  notice: 'badge-notice',
  cta: 'badge-cta',
  resources: 'badge-resources',
  priority: 'badge-priority',
  mnemonics: 'badge-mnemonics',
  study_material: 'badge-study-material',
}

/** 卡类型条目列表（供选择器使用） */
export const CARD_TYPE_OPTIONS: { key: CardType; label: string }[] =
  (Object.keys(CARD_TYPE_LABELS) as CardType[]).map(key => ({
    key,
    label: CARD_TYPE_LABELS[key],
  }))
