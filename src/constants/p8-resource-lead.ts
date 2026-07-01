import type { CardType, P8ConversionMode, P8ScriptNode } from '@/types/exam-article'

export const P8_RESOURCE_LEAD_TEMPLATE = 'resource_lead_v1'

export const P8_RESOURCE_LEAD_ASSETS = [
  '三色笔记',
  '高频考点 PDF',
  '30 天打卡表',
  '历年真题解析',
  '易混点表',
]

export const P8_RESOURCE_LEAD_COMMENT_KEYWORD = '药师资料'

export const P8_RESOURCE_LEAD_CONVERSION_MODES: P8ConversionMode[] = [
  'comment',
  'private_message',
  'collect',
]

export const P8_RESOURCE_LEAD_SCRIPT_NODES: P8ScriptNode[] = [
  {
    id: 'cover_hook',
    label: '封面钩子',
    purpose: '用资料已整理、少走弯路制造点击理由',
    cardType: 'cover',
  },
  {
    id: 'pain_point',
    label: '痛点',
    purpose: '说明目标人群为什么现在需要资料，而不是继续乱找',
    cardType: 'notice',
  },
  {
    id: 'solution',
    label: '解决方案',
    purpose: '告诉用户先固定几类资料，降低行动成本',
    cardType: 'plan',
  },
  {
    id: 'knowledge_preview',
    label: '干货预览',
    purpose: '放少量专业高频点做信任背书，不展开成讲义',
    cardType: 'priority',
  },
  {
    id: 'resource_bait',
    label: '资料诱饵',
    purpose: '展示资料清单，承接评论和私信领取动作',
    cardType: 'resources',
  },
  {
    id: 'receive_method',
    label: '领取方式',
    purpose: '引导评论关键词、私信或收藏等站内动作',
    cardType: 'cta',
  },
]

export function p8NodesToCardSequence(nodes: P8ScriptNode[]): CardType[] {
  return nodes.map(node => node.cardType)
}

export function cloneP8ResourceLeadNodes(): P8ScriptNode[] {
  return P8_RESOURCE_LEAD_SCRIPT_NODES.map(node => ({ ...node }))
}
