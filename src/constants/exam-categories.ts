import type { ExamCategory } from '@/types/topic-finder'
import type { CardType } from '@/types/exam-article'

/** 预设考试类目配置 */
export const EXAM_CATEGORIES: ExamCategory[] = [
  {
    id: 'pharmacist',
    name: '执业药师',
    examDate: '2026-10-24',
    keywords: ['执业药师', '药师', '药考', '药剂师'],
    subjects: ['药学专业知识一', '药学专业知识二', '药学综合知识与技能', '药事管理与法规'],
    recommendedPreset: ['cover', 'plan', 'plan', 'priority', 'study_material', 'notice', 'cta'] as CardType[],
  },
  {
    id: 'physician',
    name: '执业医师资格证',
    examDate: '2026-08-02',
    keywords: ['医师考试', '执业医师', '医师资格证', '临床执业'],
    subjects: ['基础医学', '临床医学', '预防医学', '医学人文'],
    recommendedPreset: ['cover', 'plan', 'plan', 'priority', 'mnemonics', 'cta'] as CardType[],
  },
  {
    id: 'nurse',
    name: '护士资格证',
    examDate: '2026-07-15',
    keywords: ['护士', '护理', '护资'],
    subjects: ['基础护理学', '内科护理学', '外科护理学', '妇产科护理学', '儿科护理学'],
    recommendedPreset: ['cover', 'plan', 'subjects', 'resources', 'cta'] as CardType[],
  },
  {
    id: 'teacher',
    name: '教师资格证',
    examDate: '2026-10-25',
    keywords: ['教资', '教师证', '教师资格'],
    subjects: ['综合素质', '教育知识与能力', '学科知识与教学能力'],
    recommendedPreset: ['cover', 'plan', 'subjects', 'notice', 'cta'] as CardType[],
  },
  {
    id: 'safety_engineer',
    name: '注册安全工程师',
    examDate: '2026-10-25',
    keywords: ['注安', '安全工程师', '注册安全'],
    subjects: ['安全生产法律法规', '安全生产管理', '安全生产技术基础', '专业实务'],
    recommendedPreset: ['cover', 'plan', 'subjects', 'mnemonics', 'resources', 'cta'] as CardType[],
  },
  {
    id: 'fire_engineer',
    name: '消防工程师',
    examDate: '2026-11-07',
    keywords: ['消防', '消防工程', '一消'],
    subjects: ['消防安全技术实务', '消防安全技术综合能力', '消防安全案例分析'],
    recommendedPreset: ['cover', 'plan', 'subjects', 'priority', 'resources', 'cta'] as CardType[],
  },
]

/** 根据 ID 查找类目 */
export function getCategoryById(id: string): ExamCategory | undefined {
  return EXAM_CATEGORIES.find(c => c.id === id)
}

/** 类目名称映射 */
export const CATEGORY_NAME_MAP: Record<string, string> = {
  pharmacist: '执业药师',
  physician: '执业医师',
  nurse: '护士资格证',
  teacher: '教师资格证',
  safety_engineer: '注册安全工程师',
  fire_engineer: '消防工程师',
}
