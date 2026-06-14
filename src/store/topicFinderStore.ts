import { create } from 'zustand'
import type { Topic, HistoryRecord } from '@/types/topic-finder'
import { EXAM_CATEGORIES } from '@/constants/exam-categories'
import { calcDaysRemaining, getCurrentPhase, generateTopics } from '@/utils/phase-engine'
import { parseHistoryMd } from '@/utils/md-parser'

interface TopicFinderState {
  // 输入
  currentCategory: string
  keyword: string

  // 分析结果
  topics: Topic[]
  isLoading: boolean
  daysRemaining: number
  currentPhase: string

  // 历史数据
  historyRecords: HistoryRecord[]
  lastUpdate: string

  // 动作
  setCategory: (id: string) => void
  setKeyword: (kw: string) => void
  triggerAnalysis: () => void
  setTopics: (topics: Topic[]) => void
  setLoading: (loading: boolean) => void

  // 历史数据管理
  uploadHistoryFile: (fileContent: string) => { count: number; errors: string[] }
  downloadTemplate: () => void
  clearHistory: () => void
}

export const useTopicFinderStore = create<TopicFinderState>((set, get) => ({
  currentCategory: 'physician',
  keyword: '',
  topics: [],
  isLoading: false,
  daysRemaining: 53,
  currentPhase: '备考中期',
  historyRecords: [],
  lastUpdate: '',

  setCategory: (id: string) => {
    set({ currentCategory: id, keyword: '' })
    get().triggerAnalysis()
  },

  setKeyword: (kw: string) => {
    set({ keyword: kw })
  },

  triggerAnalysis: () => {
    const { currentCategory, keyword, historyRecords } = get()
    set({ isLoading: true })

    // 模拟延迟后生成结果
    const delay = keyword ? 800 : 1200
    setTimeout(() => {
      const category = EXAM_CATEGORIES.find(c => c.id === currentCategory)
      if (!category) {
        set({ isLoading: false })
        return
      }

      const daysRemaining = calcDaysRemaining(category.examDate)
      const { phase } = getCurrentPhase(daysRemaining)
      const topics = generateTopics(currentCategory, daysRemaining, historyRecords, keyword)

      set({
        topics,
        daysRemaining,
        currentPhase: phase,
        isLoading: false,
      })
    }, delay)
  },

  setTopics: (topics: Topic[]) => set({ topics }),
  setLoading: (loading: boolean) => set({ isLoading: loading }),

  uploadHistoryFile: (fileContent: string) => {
    const errors: string[] = []
    let records: HistoryRecord[] = []

    try {
      records = parseHistoryMd(fileContent)
      if (records.length === 0) {
        errors.push('未识别到有效选题数据，请检查格式是否正确')
      }
    } catch {
      errors.push('文件解析失败，请确认文件为有效的 Markdown 格式')
    }

    set({
      historyRecords: records,
      lastUpdate: new Date().toISOString().split('T')[0],
    })

    return { count: records.length, errors }
  },

  downloadTemplate: () => {
    const { generateMdTemplate } = require('@/utils/md-parser')
    const template = generateMdTemplate()
    const blob = new Blob([template], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '历史选题数据模板.md'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },

  clearHistory: () => {
    set({ historyRecords: [], lastUpdate: '' })
  },
}))
