import type { HistoryRecord } from '@/types/topic-finder'
import { EXAM_CATEGORIES } from '@/constants/exam-categories'

/**
 * 解析 Markdown 格式的历史选题数据
 * 按 PRD 定义的格式逐字段提取
 */
export function parseHistoryMd(mdContent: string): HistoryRecord[] {
  const records: HistoryRecord[] = []
  // 按 "## 选题" 分割
  const sections = mdContent.split(/^## 选题 \d+$/gm).filter(s => s.trim())

  // 如果正则没分割成功，尝试按 ## 分割
  const blocks = sections.length > 0 ? sections : mdContent.split(/(?=## 选题)/)

  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i]
    if (!block.trim()) continue

    const extract = (key: string): string => {
      const regex = new RegExp(`- ${key}:\\s*(.+?)\\s*$`, 'm')
      const match = block.match(regex)
      return match ? match[1].trim() : ''
    }

    const topic = extract('选题方向')
    const noteType = extract('笔记类型')
    if (!topic) continue // 没有选题方向就跳过

    const categoryNameRaw = extract('考试类目')
    // 试着匹配类目 ID
    const matchedCategory = EXAM_CATEGORIES.find(
      c => c.name === categoryNameRaw || c.keywords.some(k => categoryNameRaw.includes(k))
    )
    const categoryId = matchedCategory?.id ?? 'unknown'

    records.push({
      id: `rec_${Date.now()}_${i}`,
      categoryId,
      topic,
      noteType: noteType || '未分类',
      account: extract('发布平台') || '未知',
      pubDate: extract('发布时间') || '',
      daysBeforeExam: parseInt(extract('距考试天数'), 10) || 0,
      likes: parseInt(extract('点赞数'), 10) || 0,
      saves: parseInt(extract('收藏数'), 10) || 0,
      comments: parseInt(extract('评论数'), 10) || 0,
      notes: extract('备注') || '',
    })
  }

  return records
}

/**
 * 生成数据模板（Markdown 格式），供运营下载填写
 */
export function generateMdTemplate(): string {
  return `# 历史成功选题记录

## 选题 1
- 考试类目: 执业医师资格证
- 选题方向: 倒计时50天高频考点速记
- 笔记类型: 考点速记
- 发布平台: 每日一题号
- 发布时间: 2025-07-15
- 距考试天数: 18天
- 点赞数: 523
- 收藏数: 312
- 评论数: 45
- 备注: 评论区大量问"有没有完整版"，留资效果好

## 选题 2
- 考试类目: 执业医师资格证
- 选题方向: 心血管系统疾病思维导图
- 笔记类型: 知识导图
- 发布平台: 医考号
- 发布时间: 2025-08-01
- 距考试天数: 1天
- 点赞数: 891
- 收藏数: 1203
- 评论数: 67
- 备注: 考前最后一天的笔记，收藏量远超平常

<!-- 按上方格式继续添加更多选题，每篇用 ## 选题 N 分隔 -->
`
}

/**
 * 统计每个类目的记录数
 */
export function countByCategory(records: HistoryRecord[]): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const r of records) {
    counts[r.categoryId] = (counts[r.categoryId] || 0) + 1
  }
  return counts
}
