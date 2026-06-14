import type { DifyGenerateParams, DifyGenerateResult, CardData, PlanDay, CardItem } from '@/types/exam-article'

/**
 * Dify Workflow API 封装（H5 专用，fetch + streaming）
 */

const DIFY_API_URL = 'http://localhost/v1/workflows/run'
const DIFY_API_KEY = 'app-SLc5nNMlGTuR8XJrEY48ssY1'

export type ProgressCallback = (step: number, label: string) => void

/**
 * 计算考试相关的时间变量（前端确定性计算，不需要 AI 推理）
 */
function computeExamTimeVars(examDate: string): {
  countdownDays: number
  phase1End: string
  phase2End: string
  today: string
} {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const exam = new Date(examDate)
  exam.setHours(0, 0, 0, 0)

  // 距离考试天数
  const countdownDays = Math.max(0, Math.ceil((exam.getTime() - today.getTime()) / 86400000))

  // 三阶段窗口反推
  // 基础阶段：today → 考前 55 天（如果时间不够则压缩）
  // 强化阶段：考前 55 天 → 考前 20 天
  // 冲刺阶段：考前 20 天 → 考试日
  const phase1EndDate = new Date(exam.getTime() - 55 * 86400000)
  const phase2EndDate = new Date(exam.getTime() - 20 * 86400000)

  // 如果基础阶段结束日已过（距离考试不足 55 天），压到 3 天后
  const p1End = phase1EndDate < today
    ? new Date(today.getTime() + 3 * 86400000)
    : phase1EndDate
  // 如果强化阶段结束日比基础阶段还早或只差 3 天，调整
  let p2End = phase2EndDate
  if (p2End <= p1End) {
    p2End = new Date(p1End.getTime() + (exam.getTime() - p1End.getTime()) * 0.6)
  }

  const fmt = (d: Date) => d.toISOString().slice(0, 10)

  return {
    countdownDays,
    phase1End: fmt(p1End),
    phase2End: fmt(p2End),
    today: fmt(today),
  }
}

function buildCardsPayload(cardSequence: DifyGenerateParams['cardSequence']) {
  return cardSequence.map(type => {
    const base = {
      type,
      title: '',
      subtitle: '',
      days: [] as PlanDay[],
      items: [] as CardItem[],
      qrcode_url: '',
    }
    if (type === 'study_material') {
      return { ...base, study_material: [] }
    }
    return base
  })
}

/**
 * 从 SSE streaming 响应中提取最终 cards
 */
async function parseSSEStream(response: Response): Promise<CardData[]> {
  const text = await response.text()
  const lines = text.split('\n')

  for (const line of lines) {
    if (!line.startsWith('data: ')) continue
    try {
      const event = JSON.parse(line.slice(6))
      if (event.event === 'workflow_finished') {
        const cards = event.data?.outputs?.cards
        if (cards && Array.isArray(cards)) {
          return cards as CardData[]
        }
      }
    } catch {
      // 跳过 ping 等非 JSON 行
    }
  }

  throw new Error('Streaming 响应中未找到 workflow_finished 事件')
}

/**
 * 调用 Dify Workflow 生成卡片内容
 *
 * 使用 fetch + streaming 模式，无超时限制，适合长时间 LLM 生成。
 */
export async function generateCards(
  params: DifyGenerateParams,
  onProgress?: ProgressCallback,
): Promise<DifyGenerateResult> {
  const { examName, examDate, cardSequence, role, targetAudience, theme, includeStudyMaterial, chapterIndex } = params

  onProgress?.(1, '🎯 正在调用 AI 生成卡片...')

  const cardsPayload = buildCardsPayload(cardSequence)

  // ★ 新增：前端计算确定性数据
  const timeVars = examDate
    ? computeExamTimeVars(examDate)
    : { countdownDays: 0, phase1End: '', phase2End: '', today: '' }

  const response = await fetch(DIFY_API_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${DIFY_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      inputs: {
        exam_name: examName,
        exam_date: examDate,
        cards: JSON.stringify(cardsPayload),
        role: role,
        // ★ 新增 4 个计算变量
        countdown_days: timeVars.countdownDays,
        phase_1_end: timeVars.phase1End,
        phase_2_end: timeVars.phase2End,
        today_date: timeVars.today,
        target_audience: targetAudience ?? '',
        theme: theme ?? '',
        include_study_material: includeStudyMaterial ?? false,
        chapter_index: chapterIndex ?? '',
      },
      response_mode: 'streaming',
      user: 'workbench-user',
    }),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Dify API 请求失败 (${response.status}): ${errorText}`)
  }

  onProgress?.(3, '⏳ AI 正在逐张生成卡片，请耐心等待...')

  const cards = await parseSSEStream(response)

  onProgress?.(5, '✅ 卡片生成完成')

  return { cards }
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
  // ── 真实 API 调用（需 Dify 单卡重写 Workflow 就绪后启用） ──
  // const response = await fetch('http://localhost/v1/workflows/run', {
  //   method: 'POST',
  //   headers: {
  //     'Authorization': `Bearer ${DIFY_API_KEY}`,
  //     'Content-Type': 'application/json',
  //   },
  //   body: JSON.stringify({
  //     inputs: {
  //       original_card: JSON.stringify(card),
  //       feedback: feedback,
  //     },
  //     response_mode: 'blocking',
  //     user: 'workbench-user',
  //   }),
  // })
  // const data = await response.json()
  // return data.data.outputs.card as CardData

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
