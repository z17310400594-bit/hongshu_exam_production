/** V3 知识库章节索引映射 */
import zhiYeYaoShiFagui from './chapter-index.json'

/** 考试名 → chapter_index.json 内容 (JSON 字符串) */
export const CHAPTER_INDEX_MAP: Record<string, string> = {
  '执业药师': JSON.stringify(zhiYeYaoShiFagui),
}

/**
 * 根据考试名获取 chapter_index
 * 仅当考试名包含已配置知识库的关键词时才返回索引内容
 * 否则返回空字符串（纯 LLM 生成）
 */
export function getChapterIndex(examName: string): string {
  for (const [key, value] of Object.entries(CHAPTER_INDEX_MAP)) {
    if (examName.includes(key)) {
      return value
    }
  }
  return ''
}
