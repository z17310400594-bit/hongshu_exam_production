import { create } from 'zustand'
import type {
  CardType, CardData, GeneratedContent, ReviewModification,
  StyleToken, ProgressStep, P8ScriptNode, P8ConversionMode,
} from '@/types/exam-article'
import { PRESET_STANDARD, PRESET_COMPACT, PRESET_WITH_STUDY } from '@/constants/card-templates'
import {
  P8_RESOURCE_LEAD_ASSETS,
  P8_RESOURCE_LEAD_COMMENT_KEYWORD,
  P8_RESOURCE_LEAD_CONVERSION_MODES,
  P8_RESOURCE_LEAD_TEMPLATE,
  cloneP8ResourceLeadNodes,
  p8NodesToCardSequence,
} from '@/constants/p8-resource-lead'
import { STYLE_TOKENS, DEFAULT_STYLE_KEY } from '@/constants/style-tokens'
import { generateCards, rewriteCard, reviseByFeedback } from '@/services/dify'
import { deepClone } from '@/utils/validation'

interface ExamArticleState {
  // 输入参数
  role: string
  certificateCode: string
  examName: string
  examDate: string
  cardSequence: CardType[]
  currentStyle: string

  // V1.1 目标人群
  targetAudience: string
  targetAudienceCustom: string

  // V1.1 主题方向
  theme: string
  themeCustom: string

  // P8 资料型引流
  contentGoal: 'resource_lead'
  structureTemplate: string
  scriptNodes: P8ScriptNode[]
  leadAssetsText: string
  commentKeyword: string
  conversionModes: P8ConversionMode[]
  manualBrief: string

  // 生成状态
  isGenerating: boolean
  progressSteps: ProgressStep[]
  isReviewing: boolean
  isGenerated: boolean

  // 生成内容
  generatedContent: GeneratedContent | null
  pendingContent: GeneratedContent | null  // 审核中的内容
  originalContent: GeneratedContent | null  // 初始快照，用于回退

  // 版本管理
  cardVersions: Record<number, CardData[]>
  activeVersions: Record<number, number>

  // 审核修改记录
  reviewModifications: ReviewModification[]
  editingCardIndex: number

  // 动作
  setRole: (role: string) => void
  setCertificateCode: (code: string) => void
  setExamName: (name: string) => void
  setExamDate: (date: string) => void
  setCardSequence: (seq: CardType[]) => void
  setCurrentStyle: (key: string) => void
  applyPreset: (count: 5 | 6 | 7) => void
  addCard: (type: CardType) => void
  removeCard: (index: number) => void
  reorderCards: (from: number, to: number) => void

  // V1.1 目标人群
  setTargetAudience: (tag: string) => void
  setTargetAudienceCustom: (text: string) => void

  // V1.1 主题方向
  setTheme: (preset: string) => void
  setThemeCustom: (text: string) => void

  // P8 资料型引流
  resetP8Structure: () => void
  setP8ScriptNodes: (nodes: P8ScriptNode[]) => void
  updateP8ScriptNode: (index: number, patch: Partial<P8ScriptNode>) => void
  removeP8ScriptNode: (index: number) => void
  addP8ScriptNode: () => void
  setLeadAssetsText: (text: string) => void
  setCommentKeyword: (text: string) => void
  toggleConversionMode: (mode: P8ConversionMode) => void
  setManualBrief: (text: string) => void

  // 生成
  startGenerate: () => Promise<void>

  // 审核
  openReview: () => void
  approveReview: () => void
  revertToOriginal: () => void
  submitReviewModification: (type: 'sensitive' | 'duplicate', feedback: string) => Promise<void>

  // 编辑
  startEditCard: (index: number) => void
  confirmEditCard: (index: number) => void
  cancelEditCard: () => void
  getEditFormValues: (index: number) => Record<string, string>
  saveEditForm: (index: number, values: Record<string, string>) => void

  // 单卡重写
  rewriteSingleCard: (index: number, feedback: string) => Promise<void>

  // 版本切换
  switchVersion: (cardIndex: number, versionIndex: number) => void

  // 获取当前显示的数据
  getCurrentCard: (index: number) => CardData | null
  getCurrentStyle: () => StyleToken | undefined
}

export const useExamArticleStore = create<ExamArticleState>((set, get) => ({
  role: '内容号',
  certificateCode: '',
  examName: '执业医师资格证',
  examDate: '2026-08-02',
  cardSequence: p8NodesToCardSequence(cloneP8ResourceLeadNodes()),
  currentStyle: DEFAULT_STYLE_KEY,

  targetAudience: '',
  targetAudienceCustom: '',
  theme: '',
  themeCustom: '',
  contentGoal: 'resource_lead',
  structureTemplate: P8_RESOURCE_LEAD_TEMPLATE,
  scriptNodes: cloneP8ResourceLeadNodes(),
  leadAssetsText: P8_RESOURCE_LEAD_ASSETS.join('、'),
  commentKeyword: P8_RESOURCE_LEAD_COMMENT_KEYWORD,
  conversionModes: [...P8_RESOURCE_LEAD_CONVERSION_MODES],
  manualBrief: '',

  isGenerating: false,
  progressSteps: [],
  isReviewing: false,
  isGenerated: false,

  generatedContent: null,
  pendingContent: null,
  originalContent: null,

  cardVersions: {},
  activeVersions: {},
  reviewModifications: [],
  editingCardIndex: -1,

  setRole: (role: string) => set({ role }),
  setCertificateCode: (code: string) => set({ certificateCode: code }),
  setExamName: (name: string) => set({ examName: name }),
  setExamDate: (date: string) => set({ examDate: date }),
  setCardSequence: (seq: CardType[]) => set({ cardSequence: seq }),
  setCurrentStyle: (key: string) => set({ currentStyle: key }),

  applyPreset: (count: 5 | 6 | 7) => {
    if (count === 5) set({ cardSequence: [...PRESET_COMPACT] })
    else if (count === 7) set({ cardSequence: [...PRESET_WITH_STUDY] })
    else set({ cardSequence: [...PRESET_STANDARD] })
  },

  addCard: (type: CardType) => {
    set(state => ({ cardSequence: [...state.cardSequence, type] }))
  },

  removeCard: (index: number) => {
    set(state => {
      if (state.cardSequence.length <= 2) return state
      const newSeq = [...state.cardSequence]
      newSeq.splice(index, 1)
      return { cardSequence: newSeq }
    })
  },

  reorderCards: (from: number, to: number) => {
    set(state => {
      const newSeq = [...state.cardSequence]
      const [moved] = newSeq.splice(from, 1)
      newSeq.splice(to, 0, moved)
      return { cardSequence: newSeq }
    })
  },

  // V1.1 目标人群：选中标签 → 清空自定义
  setTargetAudience: (tag: string) => {
    set(state => ({
      targetAudience: state.targetAudience === tag ? '' : tag,
      targetAudienceCustom: '',
    }))
  },

  // V1.1 目标人群自定义：填写 → 清空标签
  setTargetAudienceCustom: (text: string) => {
    set({ targetAudienceCustom: text, targetAudience: '' })
  },

  // V1.1 主题预设：选中 → 禁用自由输入
  setTheme: (preset: string) => {
    set({
      theme: preset,
      themeCustom: '',
    })
  },

  // V1.1 主题自定义
  setThemeCustom: (text: string) => {
    set({ themeCustom: text, theme: '' })
  },

  resetP8Structure: () => {
    const nodes = cloneP8ResourceLeadNodes()
    set({
      scriptNodes: nodes,
      cardSequence: p8NodesToCardSequence(nodes),
      structureTemplate: P8_RESOURCE_LEAD_TEMPLATE,
    })
  },

  setP8ScriptNodes: (nodes: P8ScriptNode[]) => {
    const normalized = nodes.length > 0 ? nodes : cloneP8ResourceLeadNodes()
    set({
      scriptNodes: normalized,
      cardSequence: p8NodesToCardSequence(normalized),
    })
  },

  updateP8ScriptNode: (index: number, patch: Partial<P8ScriptNode>) => {
    set(state => {
      const nodes = state.scriptNodes.map((node, i) => (i === index ? { ...node, ...patch } : node))
      return { scriptNodes: nodes, cardSequence: p8NodesToCardSequence(nodes) }
    })
  },

  removeP8ScriptNode: (index: number) => {
    set(state => {
      if (state.scriptNodes.length <= 3) return state
      const nodes = state.scriptNodes.filter((_, i) => i !== index)
      return { scriptNodes: nodes, cardSequence: p8NodesToCardSequence(nodes) }
    })
  },

  addP8ScriptNode: () => {
    set(state => {
      const nodes: P8ScriptNode[] = [
        ...state.scriptNodes,
        {
          id: `custom_${Date.now()}`,
          label: '自定义节点',
          purpose: '补充运营想强调的转化内容',
          cardType: 'notice',
        },
      ]
      return { scriptNodes: nodes, cardSequence: p8NodesToCardSequence(nodes) }
    })
  },

  setLeadAssetsText: (text: string) => set({ leadAssetsText: text }),
  setCommentKeyword: (text: string) => set({ commentKeyword: text }),
  toggleConversionMode: (mode: P8ConversionMode) => {
    set(state => {
      const exists = state.conversionModes.includes(mode)
      const next = exists
        ? state.conversionModes.filter(item => item !== mode)
        : [...state.conversionModes, mode]
      return { conversionModes: next.length > 0 ? next : ['comment'] }
    })
  },
  setManualBrief: (text: string) => set({ manualBrief: text }),

  startGenerate: async () => {
    const {
      certificateCode, examName, examDate, cardSequence,
      targetAudience, targetAudienceCustom, theme, themeCustom,
      contentGoal, structureTemplate, scriptNodes, leadAssetsText,
      commentKeyword, conversionModes, manualBrief,
    } = get()
    set({ isGenerating: true, progressSteps: [] })

    try {
      const result = await generateCards(
        {
          certificateCode,
          examName,
          examDate,
          cardSequence,
          role: get().role,
          targetAudience: targetAudience || targetAudienceCustom,
          theme: theme || themeCustom,
          contentGoal,
          structureTemplate,
          scriptNodes,
          leadAssets: leadAssetsText.split(/[、,，\n]/).map(item => item.trim()).filter(Boolean),
          commentKeyword,
          conversionModes,
          cardCount: cardSequence.length,
          manualBrief,
        },
        (step, label) => {
          set(state => ({
            progressSteps: [
              ...state.progressSteps.filter(s => s.id !== step),
              { id: step, label, status: 'current' as const },
            ].sort((a, b) => a.id - b.id),
          }))
        },
      )

      // 保存初始快照
      const content = result as GeneratedContent
      set({
        isGenerating: false,
        pendingContent: deepClone(content),
        originalContent: deepClone(content),
        reviewModifications: [],
        editingCardIndex: -1,
        isReviewing: true,
      })
    } catch (error) {
      set({ isGenerating: false })
      throw error
    }
  },

  openReview: () => set({ isReviewing: true }),

  approveReview: () => {
    const { pendingContent } = get()
    if (!pendingContent) return

    const versions: Record<number, CardData[]> = {}
    const active: Record<number, number> = {}
    pendingContent.cards.forEach((card, i) => {
      versions[i] = [deepClone(card)]
      active[i] = 0
    })

    set({
      generatedContent: deepClone(pendingContent),
      cardVersions: versions,
      activeVersions: active,
      isReviewing: false,
      isGenerated: true,
      pendingContent: null,
      originalContent: null,
      reviewModifications: [],
      editingCardIndex: -1,
    })
  },

  revertToOriginal: () => {
    const { originalContent } = get()
    if (!originalContent) return
    set({
      pendingContent: deepClone(originalContent),
      reviewModifications: [],
      editingCardIndex: -1,
    })
  },

  submitReviewModification: async (type: 'sensitive' | 'duplicate', feedback: string) => {
    const { pendingContent } = get()
    if (!pendingContent) return

    const result = await reviseByFeedback(pendingContent.cards, feedback, type)
    const modified = result.modified

    const mod: ReviewModification = {
      type,
      typeLabel: type === 'sensitive' ? '敏感词' : '查重',
      feedback,
      cardIndex: result.cardIndex,
      cardType: modified.type,
      original: deepClone(pendingContent.cards[result.cardIndex]),
      modified: deepClone(modified),
      time: new Date().toLocaleTimeString(),
    }

    const newCards = [...pendingContent.cards]
    newCards[result.cardIndex] = modified

    set({
      pendingContent: { ...pendingContent, cards: newCards },
      reviewModifications: [...get().reviewModifications, mod],
    })
  },

  startEditCard: (index: number) => set({ editingCardIndex: index }),
  confirmEditCard: (_index: number) => set({ editingCardIndex: -1 }),
  cancelEditCard: () => set({ editingCardIndex: -1 }),

  getEditFormValues: (_index: number) => {
    // 由组件自行管理编辑表单状态
    return {}
  },

  saveEditForm: (index: number, values: Record<string, string>) => {
    const { pendingContent } = get()
    if (!pendingContent) return

    const card = deepClone(pendingContent.cards[index])
    card.title = values.title || card.title
    card.subtitle = values.subtitle || card.subtitle

    const newCards = [...pendingContent.cards]
    newCards[index] = card
    set({ pendingContent: { ...pendingContent, cards: newCards } })
  },

  rewriteSingleCard: async (index: number, feedback: string) => {
    const { generatedContent, cardVersions, activeVersions } = get()
    if (!generatedContent) return

    const currentCard = cardVersions[index]?.[activeVersions[index]] ?? generatedContent.cards[index]
    const modified = await rewriteCard(currentCard, feedback)

    const newVersions = { ...cardVersions }
    if (!newVersions[index]) newVersions[index] = [deepClone(currentCard)]
    newVersions[index] = [...newVersions[index], modified]

    const newActive = { ...activeVersions, [index]: newVersions[index].length - 1 }
    const newCards = [...generatedContent.cards]
    newCards[index] = modified

    set({
      cardVersions: newVersions,
      activeVersions: newActive,
      generatedContent: { ...generatedContent, cards: newCards },
    })
  },

  switchVersion: (cardIndex: number, versionIndex: number) => {
    const { generatedContent, cardVersions, activeVersions } = get()
    if (!generatedContent || !cardVersions[cardIndex]) return

    const newActive = { ...activeVersions, [cardIndex]: versionIndex }
    const newCards = [...generatedContent.cards]
    newCards[cardIndex] = deepClone(cardVersions[cardIndex][versionIndex])

    set({
      activeVersions: newActive,
      generatedContent: { ...generatedContent, cards: newCards },
    })
  },

  getCurrentCard: (index: number) => {
    const { generatedContent, cardVersions, activeVersions } = get()
    if (!generatedContent) return null
    return cardVersions[index]?.[activeVersions[index]] ?? generatedContent.cards[index] ?? null
  },

  getCurrentStyle: () => {
    return STYLE_TOKENS.find(s => s.key === get().currentStyle)
  },
}))
