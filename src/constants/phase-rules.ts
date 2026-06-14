import type { PhaseRule } from '@/types/topic-finder'

/**
 * 考试周期规则引擎配置
 * 基于考试日期倒推天数，划分阶段并匹配推荐选题类型
 */
export const PHASE_RULES: PhaseRule[] = [
  {
    phase: '备考早期',
    daysRange: [60, 999],
    recommendedTypes: [
      { type: '报考指南', reason: '新考生占比高，用户正在搜"怎么报名""条件是什么"' },
      { type: '考试科目一览', reason: '用户需要了解考试结构和科目分布' },
      { type: '备考规划', reason: '备考早期用户最关心"能不能来得及""怎么开始"' },
      { type: '零基础入门', reason: '跨专业考生需要从零搭建知识框架' },
    ],
  },
  {
    phase: '备考中期',
    daysRange: [30, 59],
    recommendedTypes: [
      { type: '高频考点速记', reason: '用户进入系统复习阶段，搜索"重点""高频"词条明显上升' },
      { type: '知识导图', reason: '思维导图类笔记在备考中期收藏率最高，帮助建立知识体系' },
      { type: '学习计划表', reason: '用户需要阶段性学习安排来保持节奏' },
      { type: '真题命题规律', reason: '进入"听课转刷题"过渡期，用户对真题类内容兴趣上升' },
    ],
  },
  {
    phase: '冲刺期',
    daysRange: [14, 29],
    recommendedTypes: [
      { type: '高频考点速记', reason: '用户进入紧急复习模式，搜索"重点""高频"激增' },
      { type: '倒计时计划', reason: '用户需要可执行的每日学习安排，紧迫感驱动收藏' },
      { type: '考前须知', reason: '考场信息、必备物品类笔记在考前 2 周收藏量达到峰值' },
      { type: '速记口诀', reason: '冲刺阶段记忆效率是关键，口诀类内容互动率高于均值 40%' },
    ],
  },
  {
    phase: '考前',
    daysRange: [1, 13],
    recommendedTypes: [
      { type: '考前须知', reason: '考场规则、必备物品清单在考前 1 周搜索量达到峰值' },
      { type: '考前押题', reason: '用户对"押题""预测"类内容关注度最高' },
      { type: '最后梳理', reason: '考前 3 天用户需要快速过一遍核心考点' },
      { type: '心态调整', reason: '考前焦虑高峰期，情感共鸣类内容互动率高' },
    ],
  },
  {
    phase: '考后',
    daysRange: [-365, 0],
    recommendedTypes: [
      { type: '真题回忆', reason: '考后用户对真题复盘需求强烈，搜索量集中在考后 1 周' },
      { type: '成绩查询指南', reason: '考后阶段性刚需信息，长尾流量稳定' },
      { type: '下一年备考规划', reason: '未通过考生开始准备下一年，提前布局可抢占先机' },
    ],
  },
]

/**
 * 根据距考试天数计算当前所处阶段
 */
export function getPhaseByDays(daysRemaining: number): PhaseRule | undefined {
  return PHASE_RULES.find(
    rule => daysRemaining >= rule.daysRange[0] && daysRemaining <= rule.daysRange[1]
  )
}
