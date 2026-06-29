import { createGeneration } from '@/services/generationApi'
import type { DifyGenerateParams, DifyGenerateResult, CardData } from '@/types/exam-article'

/**
 * Generation API 封装。
 *
 * WP14: 浏览器不再直连 Dify，也不持有模型密钥。本文件保留原导出名，
 * 以降低页面/store 改动面；真正请求会进入后端 `/api/v2/generations`。
 */

export type ProgressCallback = (step: number, label: string) => void

/**
 * 调用后端生成服务生成卡片内容。
 */
export async function generateCards(
  params: DifyGenerateParams,
  onProgress?: ProgressCallback,
): Promise<DifyGenerateResult> {
  onProgress?.(1, '🎯 正在提交后端生成任务...')
  const result = await createGeneration(params)
  onProgress?.(5, '✅ 卡片生成完成')
  return result
}

/**
 * 单卡重写（调用 Dify 单卡重写 Workflow）
 *
 * 如果单卡重写 Workflow 尚未就绪，暂时保留 mock 逻辑作为 fallback。
 * 等 Dify 侧 Workflow 创建后，取消注释真实 API 调用分支。
 */
export async function rewriteCard(
  card: CardData,
  feedback: string,
): Promise<CardData> {
  // ── Mock Fallback（真实 API 就绪后删除此段） ──
  const modified = JSON.parse(JSON.stringify(card)) as CardData

  if (feedback.includes('周末')) {
    modified.subtitle = (modified.subtitle || '') + '（含周末复习建议）'
  }
  if (feedback.includes('题型')) {
    if (modified.items) {
      modified.items = modified.items.map(item => ({
        ...item,
        content: item.content + '（含选择题、简答题）',
      }))
    }
  }
  if (card.type === 'plan' && card.days && card.days.length > 0) {
    modified.days = card.days.map(d => ({ ...d }))
  }

  return modified
}

/**
 * 敏感词修改（Mock，等 Dify 审核 Workflow 就绪后替换）
 */
export async function reviseByFeedback(
  cards: CardData[],
  feedback: string,
  problemType: 'sensitive' | 'duplicate',
): Promise<{ cardIndex: number; modified: CardData }> {
  let targetIndex = 0

  for (let i = 0; i < cards.length; i++) {
    const card = cards[i]
    const cardText = [
      card.title, card.subtitle,
      ...(card.items ?? []).flatMap(it => [it.label, it.content]),
      ...(card.days ?? []).map(d => d.task),
    ].join(' ').toLowerCase()

    const words = feedback.split(/[，,。\s]+/).filter(w => w.length >= 2)
    if (words.some(w => cardText.includes(w.toLowerCase()))) {
      targetIndex = i
      break
    }
  }

  const modified = JSON.parse(JSON.stringify(cards[targetIndex])) as CardData

  if (problemType === 'sensitive') {
    const words = feedback.split(/[，,。\s]+/).filter(w => w.length >= 2)
    words.forEach(w => {
      const escaped = w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      const regex = new RegExp(escaped, 'g')
      modified.title = modified.title.replace(regex, '**')
      modified.subtitle = modified.subtitle.replace(regex, '**')
      if (modified.items) {
        modified.items = modified.items.map(it => ({
          ...it,
          label: it.label.replace(regex, '**'),
          content: it.content.replace(regex, '**'),
        }))
      }
      if (modified.days) {
        modified.days = modified.days.map(d => ({
          ...d,
          task: d.task.replace(regex, '**'),
        }))
      }
    })
  } else {
    modified.subtitle = (modified.subtitle || '') + '（已重写避免重复）'
    if (modified.items) {
      modified.items = modified.items.map(it => ({
        ...it,
        content: it.content + '（内容已调整）',
      }))
    }
  }

  return { cardIndex: targetIndex, modified }
}
