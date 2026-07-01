import type { CardData, GeneratedContent } from '@/types/exam-article'

/**
 * 校验生成内容
 * 返回 { errors: string[], warnings: string[] }
 */
export function validateGeneratedContent(content: GeneratedContent): {
  errors: string[]
  warnings: string[]
} {
  const errors: string[] = []
  const warnings: string[] = []

  if (!content.cards || content.cards.length === 0) {
    errors.push('生成内容为空，未包含任何卡片')
    return { errors, warnings }
  }

  content.cards.forEach((card, i) => {
    const prefix = `第 ${i + 1} 张卡片`

    // 标题不能为空
    if (!card.title || !card.title.trim()) {
      errors.push(`${prefix}：标题为空`)
    }

    // 检查 Markdown 残留
    const mdPatterns = /[*_#\[\]`>|]/
    const allText = [card.title, card.subtitle, card.mentor_note,
      ...(card.items ?? []).flatMap(it => [it.label, it.content]),
      ...(card.days ?? []).map(d => d.task),
      ...(card.study_material ?? []).flatMap(mod => [
        mod.module_title,
        ...(mod.key_points ?? []),
        ...(mod.memory_tips ?? []),
      ]),
    ].join(' ')
    if (mdPatterns.test(allText)) {
      warnings.push(`${prefix}：文字中包含 Markdown 语法残留（*_#[] 等），请检查`)
    }

    // 检查乱码字符
    const garbledPattern = /[\x00-\x08\x0B\x0C\x0E-\x1F]/
    if (garbledPattern.test(allText)) {
      errors.push(`${prefix}：文字中包含异常控制字符`)
    }

    // plan 类型检查日期（排除省略占位行）
    if (card.type === 'plan' && card.days && card.days.length > 0) {
      const dates = card.days.map(d => d.date).filter(d => d && d !== '...')
      const uniqueDates = new Set(dates)
      if (uniqueDates.size !== dates.length) {
        warnings.push(`${prefix}：学习计划中存在重复日期`)
      }
    }
  })

  return { errors, warnings }
}

/**
 * 深度克隆
 */
export function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj))
}

/**
 * HTML 转义
 */
export function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }
  return text.replace(/[&<>"']/g, c => map[c] || c)
}

/**
 * 获取卡片纯文本内容（用于文本审核展示）
 */
export function getCardPlainText(card: CardData): string {
  const lines: string[] = []
  if (card.type === 'cover' && card.title) lines.push(card.title)
  if (card.subtitle) lines.push(card.subtitle)
  if (card.body) lines.push(card.body)

  if (card.type === 'plan' && card.days && card.days.length > 0) {
    lines.push('')
    card.days.filter(d => d.date !== '...').forEach(d => {
      lines.push(`  ${d.date} ${d.weekday} · ${d.task}（${d.duration}）`)
    })
  }

  if (['subjects', 'notice', 'resources', 'priority', 'mnemonics'].includes(card.type) && card.items && card.items.length > 0) {
    lines.push('')
    card.items.forEach(item => {
      lines.push(`  ● ${item.label}：${item.content}`)
    })
  }

  if (card.type === 'study_material' && card.study_material && card.study_material.length > 0) {
    lines.push('')
    card.study_material.forEach(mod => {
      lines.push(`  📚 ${mod.module_title}`)
      if (mod.key_points && mod.key_points.length > 0) {
        mod.key_points.forEach(kp => { lines.push(`    • ${kp}`) })
      }
      if (mod.memory_tips && mod.memory_tips.length > 0) {
        lines.push(`    💡 记忆方法：${mod.memory_tips.join('；')}`)
      }
    })
  }

  if (card.cta) {
    lines.push('')
    lines.push(card.cta)
  }

  if (card.auditFlags && card.auditFlags.length > 0) {
    lines.push('')
    lines.push('审核提示：')
    card.auditFlags.forEach(flag => lines.push(`  - ${flag}`))
  }

  return lines.join('\n')
}
