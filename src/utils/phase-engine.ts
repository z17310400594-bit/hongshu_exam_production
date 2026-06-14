import type { PhaseRule, PhaseName, HistoryRecord, Topic, AnalysisReason } from '@/types/topic-finder'
import { getPhaseByDays } from '@/constants/phase-rules'
import { EXAM_CATEGORIES } from '@/constants/exam-categories'

/** 计算距考试剩余天数 */
export function calcDaysRemaining(examDate: string): number {
  const diff = Math.ceil((new Date(examDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
  return diff
}

/** 获取当前考试阶段 */
export function getCurrentPhase(daysRemaining: number): { phase: PhaseName; rule: PhaseRule | undefined } {
  const rule = getPhaseByDays(daysRemaining)
  return { phase: rule?.phase ?? '备考中期', rule }
}

/** 根据类目和历史数据生成选题推荐 */
export function generateTopics(
  categoryId: string,
  daysRemaining: number,
  historyRecords: HistoryRecord[],
  keyword?: string,
): Topic[] {
  const category = EXAM_CATEGORIES.find(c => c.id === categoryId)
  const categoryName = category?.name ?? categoryId
  const { phase, rule } = getCurrentPhase(daysRemaining)

  const topics: Topic[] = []
  const phaseTypes = rule?.recommendedTypes ?? []

  // 过滤该类目下的历史记录
  const categoryRecords = historyRecords.filter(r => r.categoryId === categoryId)

  // 为每个推荐类型生成选题
  phaseTypes.slice(0, 5).forEach((pt, index) => {
    const reasons: AnalysisReason[] = []

    // 周期规则依据
    reasons.push({ source: 'phase', text: pt.reason })

    // 内部历史数据依据
    if (categoryRecords.length > 0) {
      const matchedRecords = categoryRecords.filter(r => r.noteType === pt.type)
      if (matchedRecords.length > 0) {
        const avgSaves = Math.round(
          matchedRecords.reduce((sum, r) => sum + r.saves, 0) / matchedRecords.length
        )
        reasons.push({
          source: 'internal',
          text: `公司历史发布中，「${pt.type}」类笔记共 ${matchedRecords.length} 篇，平均收藏 ${avgSaves}，高于账号整体均值`,
        })
      } else {
        reasons.push({
          source: 'internal',
          text: `公司历史发布中该类目共 ${categoryRecords.length} 条成功记录，可作为内容方向参考`,
        })
      }
    }

    // 构造选题标题
    let title = ''
    const keywordPart = keyword ? `${keyword}` : categoryName
    switch (pt.type) {
      case '高频考点速记':
        title = `倒计时 ${daysRemaining} 天！${keywordPart}高频考点速记`
        break
      case '考试科目一览':
        title = `${keywordPart}考试科目全解析：一篇搞懂考什么、怎么考`
        break
      case '备考规划':
      case '零基础入门':
        title = `每天 2 小时！${keywordPart}从零开始的备考时间规划表`
        break
      case '学习计划表':
        title = `${keywordPart}${daysRemaining} 天冲刺学习计划，每天跟学不迷路`
        break
      case '知识导图':
        title = `${keywordPart}核心考点思维导图（${category?.subjects?.slice(0, 2).join(' + ') ?? ''}）`
        break
      case '真题命题规律':
        title = `刷题党必备！${keywordPart}历年真题命题规律总结`
        break
      case '速记口诀':
        title = `${keywordPart}速记口诀大全，${category?.subjects?.[0] ?? '核心考点'}一网打尽`
        break
      case '倒计时计划':
        title = `距考试仅剩 ${daysRemaining} 天！${keywordPart}每日学习计划表`
        break
      case '考前须知':
        title = `${keywordPart}考前必看！考试时间 + 必备物品清单`
        break
      case '考前押题':
        title = `${keywordPart}考前终极预测，这些考点今年必考`
        break
      case '最后梳理':
        title = `考前 3 天！${keywordPart}最后一轮核心考点梳理`
        break
      case '心态调整':
        title = `${keywordPart}考前焦虑怎么办？过来人的 5 条心态调整建议`
        break
      default:
        title = `${keywordPart}${pt.type}（${phase}）`
    }

    // 根据依据数量确定推荐强度
    let confidence: 'high' | 'medium' | 'low' = 'low'
    if (reasons.length >= 3) confidence = 'high'
    else if (reasons.length === 2) confidence = 'medium'

    topics.push({
      rank: index + 1,
      title,
      confidence,
      reasons,
    })
  })

  return topics.slice(0, 5)
}
