import { View, Text } from '@tarojs/components'
import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import { useExamArticleStore } from '@/store/examArticleStore'
import type { CardData } from '@/types/exam-article'
import { STYLE_TOKENS } from '@/constants/style-tokens'
import { PRESET_PLAN_TYPE, PRESET_KNOWLEDGE_TYPE } from '@/constants/card-templates'
import { getCardPlainText, deepClone, validateGeneratedContent } from '@/utils/validation'
import { copyToClipboard } from '@/utils/clipboard'
import { useCardExport } from '@/hooks/useCardExport'
import { useCertPresets } from '@/hooks/useCertPresets'
import { TARGET_AUDIENCES, THEME_PRESETS } from '@/constants/audience-theme'
import { CARD_TYPE_LABELS, CARD_TYPE_BADGES, CARD_TYPE_OPTIONS } from '@/constants/card-type-labels'
import './index.scss'

function getCountdown(examDate: string): string {
  if (!examDate) return '? 天'
  const diff = Math.ceil((new Date(examDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
  return diff > 0 ? diff + ' 天' : '已过期'
}

export default function ExamArticle() {
  const store = useExamArticleStore()
  const { exportAll, exportSingle, exportLayered } = useCardExport()
  const { certOptions, loading: certsLoading, isV2Enabled, resolveExamDate } = useCertPresets()

  // 本地 UI 状态
  const [showConfirm, setShowConfirm] = useState(false)
  const [showRewrite, setShowRewrite] = useState(false)
  const [rewriteIndex, setRewriteIndex] = useState(-1)
  const [rewriteFeedback, setRewriteFeedback] = useState('')
  const [accordionOpen, setAccordionOpen] = useState(false)
  const [toastMsg, setToastMsg] = useState('')
  const [exporting, setExporting] = useState(false)
  const [examMode, setExamMode] = useState<'preset' | 'custom'>('preset')
  const [selectedPreset, setSelectedPreset] = useState(certOptions[0]?.id ?? '')
  const defaultThemeAppliedRef = useRef(false)
  const initialCertificateAppliedRef = useRef(false)

  // 初始化：默认选中第一个主题方向
  useEffect(() => {
    if (!defaultThemeAppliedRef.current && THEME_PRESETS.length > 0 && !store.theme) {
      defaultThemeAppliedRef.current = true
      store.setTheme(THEME_PRESETS[0])
    }
  }, [store])

  // DB 证书加载完成后自动选中第一条
  useEffect(() => {
    let cancelled = false
    if (
      !initialCertificateAppliedRef.current
      && !certsLoading
      && certOptions.length > 0
      && !selectedPreset
      && examMode === 'preset'
    ) {
      const firstCat = certOptions[0]
      initialCertificateAppliedRef.current = true
      setSelectedPreset(firstCat.id)
      store.setCertificateCode(firstCat.id)
      store.setExamName(firstCat.name)
      store.setExamDate(firstCat.examDate)
      resolveExamDate(firstCat.id).then(date => {
        if (!cancelled && date && initialCertificateAppliedRef.current) store.setExamDate(date)
      })
    }
    return () => { cancelled = true }
  }, [certsLoading, certOptions, selectedPreset, examMode, resolveExamDate, store])
  const [reviewFeedback, setReviewFeedback] = useState('')
  const [reviewProblemType, setReviewProblemType] = useState<'sensitive' | 'duplicate'>('sensitive')
  // V1.1 校验
  const [themeError, setThemeError] = useState(false)
  const [audienceError, setAudienceError] = useState(false)
  // V1.1 审核 Dialog 中学习资料卡片展开状态
  const [expandedStudyCards, setExpandedStudyCards] = useState<Set<number>>(new Set())
  // 添加卡片 Dialog
  const [showAddCard, setShowAddCard] = useState(false)
  // 编辑模式本地状态
  const [editValues, setEditValues] = useState<Record<string, string>>({})

  // 内容校验结果（审核时自动计算）
  const validationResult = useMemo(() => {
    if (!store.pendingContent) return null
    return validateGeneratedContent(store.pendingContent)
  }, [store.pendingContent])

  // 检查单张卡片是否有校验问题
  const getCardIssues = useCallback((cardIndex: number): { type: 'error' | 'warn'; msg: string }[] => {
    if (!validationResult) return []
    const issues: { type: 'error' | 'warn'; msg: string }[] = []
    const prefix = `第 ${cardIndex + 1} 张卡片`
    for (const err of validationResult.errors) {
      if (err.startsWith(prefix)) issues.push({ type: 'error' as const, msg: err.replace(prefix + '：', '') })
    }
    for (const warn of validationResult.warnings) {
      if (warn.startsWith(prefix)) issues.push({ type: 'warn' as const, msg: warn.replace(prefix + '：', '') })
    }
    return issues
  }, [validationResult])

  // 当前样式 CSS 变量
  const styleVars = useMemo(() => {
    const style = STYLE_TOKENS.find(s => s.key === store.currentStyle)
    return style?.cssVars ?? {}
  }, [store.currentStyle])

  // 拖拽排序
  const dragSrcRef = { current: -1 }

  // ========== 生成流程 ==========
  const handleGenerate = useCallback(() => {
    let hasError = false

    if (!store.targetAudience && !store.targetAudienceCustom.trim()) {
      setAudienceError(true)
      hasError = true
    } else {
      setAudienceError(false)
    }

    if (!store.theme && !store.themeCustom.trim()) {
      setThemeError(true)
      hasError = true
    } else {
      setThemeError(false)
    }

    if (hasError) return
    setShowConfirm(true)
  }, [store.theme, store.themeCustom, store.targetAudience, store.targetAudienceCustom])

  const startGenerate = useCallback(async () => {
    setShowConfirm(false)
    try {
      await store.startGenerate()
    } catch (error) {
      const message = error instanceof Error ? error.message : '请稍后重试'
      setToastMsg(`❌ 生成失败：${message}`)
      setTimeout(() => setToastMsg(''), 3000)
    }
  }, [store])

  // ========== 审核 ==========
  const approveReview = useCallback(() => {
    const citations = store.pendingContent?.cards.flatMap(card => card.citations ?? []) ?? []
    if (citations.length === 0) {
      setToastMsg('❌ 当前生成结果没有资料引用，不能通过审核')
      setTimeout(() => setToastMsg(''), 2000)
      return
    }
    store.approveReview()
  }, [store])

  const submitReviewModification = useCallback(async () => {
    if (!reviewFeedback.trim()) {
      alert('请填写具体的修改意见（敏感词或重复内容）')
      return
    }
    await store.submitReviewModification(reviewProblemType, reviewFeedback.trim())
    setReviewFeedback('')
  }, [reviewFeedback, reviewProblemType, store])

  const revertToOriginal = useCallback(() => {
    if (!confirm('确定要回退到初始生成版本吗？\n\n所有修改将丢失，恢复为 AI 最初生成的内容。')) return
    store.revertToOriginal()
  }, [store])

  // ========== 编辑 ==========
  const startEditCard = useCallback((index: number) => {
    store.startEditCard(index)
    const card = store.pendingContent?.cards[index]
    if (card) {
      const vals: Record<string, string> = {
        [`title_${index}`]: card.title || '',
        [`subtitle_${index}`]: card.subtitle || '',
      }
      if (card.type === 'plan' && card.days) {
        vals[`days_${index}`] = card.days.filter(d => d.date !== '...').map(d => `${d.date} ${d.weekday} · ${d.task}（${d.duration}）`).join('\n')
      }
      if (['subjects', 'notice', 'resources', 'priority', 'mnemonics'].includes(card.type) && card.items) {
        vals[`items_${index}`] = card.items.map(it => `${it.label}：${it.content}`).join('\n')
      }
      if (card.type === 'study_material' && card.study_material) {
        vals[`study_material_${index}`] = card.study_material.map(mod =>
          `【${mod.module_title}】\n考点：${(mod.key_points ?? []).join('；')}\n记忆方法：${(mod.memory_tips ?? []).join('；')}`
        ).join('\n\n')
      }
      setEditValues(vals)
    }
  }, [store])

  const confirmEditCard = useCallback((index: number) => {
    if (!store.pendingContent) return
    const card = deepClone(store.pendingContent.cards[index])
    const title = editValues[`title_${index}`] ?? card.title
    const subtitle = editValues[`subtitle_${index}`] ?? card.subtitle
    card.title = title
    card.subtitle = subtitle

    if (card.type === 'plan') {
      const daysText = editValues[`days_${index}`] ?? ''
      if (daysText.trim()) {
        const lines = daysText.trim().split('\n').filter(l => l.trim())
        card.days = lines.map(line => {
          const match = line.match(/^(\d+\.\d+)\s+(周[一二三四五六日])\s*·\s*(.+?)[（(](.+?)[）)]$/)
          if (match) return { date: match[1], weekday: match[2], task: match[3].trim(), duration: match[4] }
          return { date: '?', weekday: '?', task: line.trim(), duration: '?' }
        })
      }
    }

    if (['subjects', 'notice', 'resources', 'priority', 'mnemonics'].includes(card.type)) {
      const itemsText = editValues[`items_${index}`] ?? ''
      if (itemsText.trim()) {
        const lines = itemsText.trim().split('\n').filter(l => l.trim())
        card.items = lines.map(line => {
          const idx = line.indexOf('：') >= 0 ? line.indexOf('：') : line.indexOf(':')
          if (idx > 0) return { label: line.substring(0, idx).trim(), content: line.substring(idx + 1).trim() }
          return { label: line.trim(), content: '' }
        })
      }
    }

    if (card.type === 'study_material') {
      const smText = editValues[`study_material_${index}`] ?? ''
      if (smText.trim()) {
        const parsed: typeof card.study_material = []
        // Parse format: 【Module Title】\n考点：...\n记忆方法：...
        const blocks = smText.trim().split(/\n(?=【)/)
        for (const block of blocks) {
          const titleMatch = block.match(/【(.+?)】/)
          const kpMatch = block.match(/考点[：:](.+?)(?:\n记忆方法|$)/s)
          const mtMatch = block.match(/记忆方法[：:](.+?)$/s)
          if (titleMatch) {
            parsed.push({
              module_title: titleMatch[1].trim(),
              key_points: kpMatch ? kpMatch[1].split(/[；;]/).map(s => s.trim()).filter(Boolean) : [],
              memory_tips: mtMatch ? mtMatch[1].split(/[；;]/).map(s => s.trim()).filter(Boolean) : [],
            })
          }
        }
        if (parsed.length > 0) card.study_material = parsed
      }
    }

    // 更新 pendingContent
    const newCards = [...store.pendingContent.cards]
    newCards[index] = card

    // 通过 store 更新
    const { useExamArticleStore: useStore } = require('@/store/examArticleStore')
    useStore.setState({
      pendingContent: { ...store.pendingContent, cards: newCards },
      editingCardIndex: -1,
    })
    setEditValues({})
  }, [store, editValues])

  const cancelEditCard = useCallback(() => {
    if (Object.keys(editValues).length > 0) {
      if (!confirm('放弃当前编辑内容？已输入的内容将丢失。')) return
    }
    store.cancelEditCard()
    setEditValues({})
  }, [store, editValues])

  // ========== 单卡重写 ==========
  const openRewrite = useCallback((index: number) => {
    setRewriteIndex(index)
    setRewriteFeedback('')
    setShowRewrite(true)
  }, [])

  const submitRewrite = useCallback(async () => {
    if (!rewriteFeedback.trim()) { alert('请输入修改意见'); return }
    await store.rewriteSingleCard(rewriteIndex, rewriteFeedback.trim())
    setShowRewrite(false)
    setRewriteIndex(-1)
  }, [rewriteFeedback, rewriteIndex, store])

  // ========== 渲染卡片预览 ==========
  const renderCardPreview = useCallback((cardData: CardData, index: number, hasVersions: boolean, currentVer: number) => {
    const displayCard = cardData
    let bodyHtml: React.ReactNode = null

    switch (displayCard.type) {
      case 'cover':
        bodyHtml = (
          <View>
            <Text className='card-title' style={{ fontSize: styleVars['--title-size'] }}>{displayCard.title}</Text>
            <Text className='card-subtitle'>{displayCard.subtitle}</Text>
            <View className='card-countdown'>
              <Text>{getCountdown(store.examDate)}</Text>
            </View>
          </View>
        )
        break
      case 'plan':
        bodyHtml = (
          <View>
            <Text className='card-subtitle'>{displayCard.subtitle}</Text>
            {displayCard.mentor_note && (
              <View className='mentor-note'>
                <Text className='mentor-note-text'>💬 {displayCard.mentor_note}</Text>
              </View>
            )}
            <View className='card-divider' />
            <View className='plan-list'>
              {/* 过滤省略占位行（摘要模式下 CODE_1 插入的 "..." 日期），避免预览出现空行 */}
              {(displayCard.days ?? [])
                .filter(d => d.date !== '...' && (d.date?.trim() || d.task?.trim() || d.duration?.trim()))
                .slice(0, 8).map((d, di) => (
                <View key={di} className={`day-row ${d.duration === '休息' ? 'rest' : ''}`}>
                  <Text className='day-date'>{d.date}</Text>
                  <Text className='day-task'>{d.task}</Text>
                  {d.duration?.trim() && <Text className='day-dur'>{d.duration}</Text>}
                </View>
              ))}
              {(displayCard.days ?? []).filter(d => d.date !== '...' && (d.date?.trim() || d.task?.trim() || d.duration?.trim())).length > 8 && (
                <Text className='day-more'>... 共 {(displayCard.days ?? []).filter(d => d.date !== '...' && (d.date?.trim() || d.task?.trim() || d.duration?.trim())).length} 天</Text>
              )}
            </View>
          </View>
        )
        break
      case 'subjects':
        bodyHtml = (
          <View>
            <Text className='card-subtitle'>{displayCard.subtitle}</Text>
            <View className='card-divider' />
            <View className='tag-list'>
              {(displayCard.items ?? []).map((item, ii) => (
                <Text key={ii} className='tag'>{item.label}</Text>
              ))}
            </View>
            <View className='items-detail'>
              {(displayCard.items ?? []).map((item, ii) => (
                <Text key={ii} className='item-line'><strong>{item.label}：</strong>{item.content}</Text>
              ))}
            </View>
          </View>
        )
        break
      case 'notice':
        bodyHtml = (
          <View>
            <Text className='card-subtitle'>{displayCard.subtitle}</Text>
            <View className='card-divider' />
            <View className='notice-list'>
              {(displayCard.items ?? []).map((item, ii) => (
                <View key={ii} className='notice-item'>
                  <View className='notice-icon'><Text>{ii + 1}</Text></View>
                  <Text className='notice-text'><strong>{item.label}</strong>：{item.content}</Text>
                </View>
              ))}
            </View>
          </View>
        )
        break
      case 'cta':
        bodyHtml = (
          <View className='cta-block'>
            <Text className='cta-sub'>{displayCard.subtitle}</Text>
            <View className='qr-placeholder'><Text>二维码</Text></View>
            <Text className='qr-hint'>评论区互动留资</Text>
          </View>
        )
        break
      case 'resources':
        bodyHtml = (
          <View>
            <Text className='card-subtitle'>{displayCard.subtitle}</Text>
            <View className='card-divider' />
            <View className='resource-list'>
              {(displayCard.items ?? []).map((item, ii) => (
                <View key={ii} className='resource-item'>
                  <Text className='resource-name'>📄 {item.label}.pdf</Text>
                  <Text className='resource-desc'>{item.content}</Text>
                </View>
              ))}
            </View>
            <Text className='resource-hint'>📥 以上资料都整理好了，评论区滴滴我</Text>
          </View>
        )
        break
      case 'priority':
        bodyHtml = (
          <View>
            <Text className='card-subtitle'>{displayCard.subtitle}</Text>
            <View className='card-divider' />
            <View className='priority-list'>
              {(displayCard.items ?? []).map((item, ii) => {
                // 分值信号用不同颜色：🔴 高分 🟡 中分 ⚪ 低分
                const scoreMatch = item.label?.match(/约?\s*(\d+)\s*分/)
                const score = scoreMatch ? parseInt(scoreMatch[1], 10) : 0
                let barColor = 'tier-low'
                if (score >= 25) barColor = 'tier-high'
                else if (score >= 10) barColor = 'tier-mid'

                return (
                  <View key={ii} className={`priority-item ${barColor}`}>
                    <View className='priority-rank'>
                      <Text className='rank-num'>{ii + 1}</Text>
                    </View>
                    <View className='priority-body'>
                      <Text className='priority-label'>{item.label}</Text>
                      <Text className='priority-content'>{item.content}</Text>
                    </View>
                  </View>
                )
              })}
            </View>
          </View>
        )
        break
      case 'mnemonics':
        bodyHtml = (
          <View>
            <Text className='card-subtitle'>{displayCard.subtitle}</Text>
            <View className='card-divider' />
            <View className='mnemonic-list'>
              {(displayCard.items ?? []).map((item, ii) => (
                <View key={ii} className='mnemonic-item'>
                  <View className='mnemonic-phrase'>
                    <Text className='mnemonic-quote'>&ldquo;</Text>
                    <Text className='mnemonic-text'>{item.label}</Text>
                    <Text className='mnemonic-quote'>&rdquo;</Text>
                  </View>
                  <View className='mnemonic-map'>
                    {item.content.split(/[,，、]/).map((part, pi) => (
                      <Text key={pi} className='map-chip'>{part.trim()}</Text>
                    ))}
                  </View>
                </View>
              ))}
            </View>
          </View>
        )
        break
      case 'study_material':
        bodyHtml = (
          <View>
            <Text className='card-subtitle'>{displayCard.subtitle}</Text>
            <View className='card-divider' />
            {(displayCard.study_material ?? []).map((mod, mi) => (
              <View key={mi} className='study-module'>
                <Text className='module-title'>📚 {mod.module_title}</Text>
                <View className='key-points'>
                  {(mod.key_points ?? []).map((kp, ki) => (
                    <Text key={ki} className='key-point'>• {kp}</Text>
                  ))}
                </View>
                {mod.memory_tips && mod.memory_tips.length > 0 && (
                  <View className='memory-tips'>
                    <Text className='tips-label'>💡 记忆方法：</Text>
                    {(mod.memory_tips ?? []).map((tip, ti) => (
                      <Text key={ti} className='tip-item'>{tip}</Text>
                    ))}
                  </View>
                )}
                {mod.source && (
                  <Text className='source-tag'>来源：{mod.source === 'knowledge_base' ? '知识库' : 'LLM 搜索'}</Text>
                )}
              </View>
            ))}
          </View>
        )
        break
    }

    return (
      <View
        key={index}
        className={`card-preview ${!store.isGenerated ? 'skeleton' : ''}`}
        {...{ 'data-card-index': index } as any}
        style={{
          borderRadius: styleVars['--card-radius'],
          background: styleVars['--card-bg'],
          backgroundImage: styleVars['--card-bg-gradient'],
          boxShadow: styleVars['--shadow'],
        } as React.CSSProperties}
        onClick={() => {
          const cards = document.querySelectorAll('.card-preview')
          cards.forEach(c => { (c as HTMLElement).style.borderColor = 'transparent' })
        }}
      >
        {store.isGenerated && (
          <View className='card-actions'>
            <button className='btn-rewrite-mini' onClick={(e) => { e.stopPropagation(); openRewrite(index) }}>🔄</button>
          </View>
        )}
        {bodyHtml}
        {hasVersions && (
          <View className='version-toggle'>
            {store.cardVersions[index].map((_, vi) => (
              <button
                key={vi}
                className={`ver-btn ${vi === currentVer ? 'active' : ''}`}
                onClick={(e) => { e.stopPropagation(); store.switchVersion(index, vi) }}
              >
                V{vi + 1}
              </button>
            ))}
          </View>
        )}
      </View>
    )
  }, [store, styleVars])

  // ========== 渲染审核文本 ==========
  const renderReviewCards = useCallback(() => {
    if (!store.pendingContent) return null
    return store.pendingContent.cards.map((card, i) => {
      const isEditing = store.editingCardIndex === i
      const text = getCardPlainText(card)

      const cardIssues = getCardIssues(i)

      if (isEditing) {
        return (
          <View key={i} className={`review-card-block editing ${cardIssues.some(iss => iss.type === 'error') ? 'has-error' : ''}`}>
            <View className='review-card-header'>
              <View className={`card-type-badge ${CARD_TYPE_BADGES[card.type] || ''}`}>
                {CARD_TYPE_LABELS[card.type] || card.type}
              </View>
              <Text>第 {i + 1} 张</Text>
              {cardIssues.length > 0 && (
                <View className='validation-issues'>
                  {cardIssues.map((iss, ji) => (
                    <Text key={ji} className={`issue-tag ${iss.type}`}>{iss.type === 'error' ? '🔴' : '🟡'} {iss.msg}</Text>
                  ))}
                </View>
              )}
              <View className='header-spacer' />
              <button className='btn-confirm-edit' onClick={() => confirmEditCard(i)}>✅ 确认修改</button>
              <button className='btn-cancel-edit' onClick={cancelEditCard}>❌ 取消</button>
            </View>
            <View className='review-edit-form'>
              {card.type === 'cover' && (
                <label className='edit-label'>
                  标题（title）
                  <textarea
                    rows={2}
                    value={editValues[`title_${i}`] ?? card.title}
                    onChange={(e) => setEditValues(prev => ({ ...prev, [`title_${i}`]: e.target.value }))}
                  />
                </label>
              )}
              <label className='edit-label'>
                副标题（subtitle）
                <input
                  value={editValues[`subtitle_${i}`] ?? card.subtitle}
                  onChange={(e) => setEditValues(prev => ({ ...prev, [`subtitle_${i}`]: e.target.value }))}
                />
              </label>
              {card.type === 'plan' && (
                <label className='edit-label'>
                  学习日程（days）
                  <textarea
                    rows={5}
                    value={editValues[`days_${i}`] ?? ((card.days ?? []).filter(d => d.date !== '...').map(d => `${d.date} ${d.weekday} · ${d.task}（${d.duration}）`).join('\n'))}
                    onChange={(e) => setEditValues(prev => ({ ...prev, [`days_${i}`]: e.target.value }))}
                  />
                </label>
              )}
              {['subjects', 'notice', 'resources', 'priority', 'mnemonics'].includes(card.type) && (
                <label className='edit-label'>
                  条目列表（items）
                  <textarea
                    rows={4}
                    value={editValues[`items_${i}`] ?? ((card.items ?? []).map(it => `${it.label}：${it.content}`).join('\n'))}
                    onChange={(e) => setEditValues(prev => ({ ...prev, [`items_${i}`]: e.target.value }))}
                  />
                </label>
              )}
              {card.type === 'study_material' && (
                <label className='edit-label'>
                  学习资料（study_material）
                  <textarea
                    rows={6}
                    value={editValues[`study_material_${i}`] ?? ((card.study_material ?? []).map(mod =>
                      `【${mod.module_title}】\n考点：${(mod.key_points ?? []).join('；')}\n记忆方法：${(mod.memory_tips ?? []).join('；')}`
                    ).join('\n\n'))}
                    onChange={(e) => setEditValues(prev => ({ ...prev, [`study_material_${i}`]: e.target.value }))}
                  />
                </label>
              )}
            </View>
          </View>
        )
      }

      return (
        <View key={i} className={`review-card-block ${cardIssues.some(iss => iss.type === 'error') ? 'has-error' : ''}`}>
          <View className='review-card-header'>
            <View className={`card-type-badge ${CARD_TYPE_BADGES[card.type] || ''}`}>
              {CARD_TYPE_LABELS[card.type] || card.type}
            </View>
            {/* <Text>第 {i + 1} 张</Text> */}
            {cardIssues.length > 0 && (
              <View className='validation-issues'>
                {cardIssues.map((iss, ji) => (
                  <Text key={ji} className={`issue-tag ${iss.type}`}>{iss.type === 'error' ? '🔴' : '🟡'} {iss.msg}</Text>
                ))}
              </View>
            )}
            <View className='header-spacer' />
            <button className='btn-copy-text' onClick={() => { copyToClipboard(text) }}>复制</button>
            <button className='btn-edit-card' onClick={() => startEditCard(i)}>编辑</button>
          </View>
          {card.type === 'study_material' ? (
            expandedStudyCards.has(i) ? (
              <View>
                <Text className='review-text-block'>{text}</Text>
                <button
                  className='btn-expand-review'
                  onClick={() => setExpandedStudyCards(prev => { const next = new Set(prev); next.delete(i); return next })}
                >
                  ▲ 收起
                </button>
              </View>
            ) : (
              <View>
                <View className='review-text-block collapsed-summary'>
                  {(card.study_material ?? []).map((mod, mi) => (
                    <Text key={mi} className='collapsed-module'> {mod.module_title}{mi < (card.study_material ?? []).length - 1 ? ' | ' : ''}</Text>
                  ))}
                </View>
                <button
                  className='btn-expand-review'
                  onClick={() => setExpandedStudyCards(prev => { const next = new Set(prev); next.add(i); return next })}
                >
                  ▼ 点击展开学习资料详情
                </button>
              </View>
            )
          ) : (
            <Text className='review-text-block'>{text}</Text>
          )}
        </View>
      )
    })
  }, [store, editValues, startEditCard, confirmEditCard, cancelEditCard, getCardIssues, expandedStudyCards])

  // ========== 主渲染 ==========
  return (
    <View
      className='exam-article'
      style={{
        '--card-bg': styleVars['--card-bg'],
        '--card-bg-gradient': styleVars['--card-bg-gradient'],
        '--title-color': styleVars['--title-color'],
        '--title-size': styleVars['--title-size'],
        '--body-color': styleVars['--body-color'],
        '--body-size': styleVars['--body-size'],
        '--accent-color': styleVars['--accent-color'],
        '--tag-bg': styleVars['--tag-bg'],
        '--tag-color': styleVars['--tag-color'],
        '--divider-color': styleVars['--divider-color'],
        '--card-radius': styleVars['--card-radius'],
        '--shadow': styleVars['--shadow'],
      } as React.CSSProperties}
    >
      {/* Toast */}
      {toastMsg && <View className='export-toast show'>{toastMsg}</View>}

      {/* ===== 左栏 ===== */}
      <View className='ea-sidebar'>
        <View className='sidebar-header'>
          <Text className='sidebar-title'>图文生成</Text>
          <Text className='sidebar-desc'>小红书 · 多图轮播</Text>
        </View>

        <View className='sidebar-body'>
          {/* 角色 */}
          <View className='form-group'>
            <Text className='form-label'>当前角色</Text>
            <select
              className='form-select'
              value={store.role}
              onChange={(e) => store.setRole(e.target.value)}
            >
              <option>内容号</option>
              <option>陪考号</option>
              <option>分析号</option>
            </select>
          </View>

          {/* 考试预设下拉 */}
          <View className='form-group'>
            <Text className='form-label'>考试类型{isV2Enabled ? '（V2）' : '（旧接口）'}</Text>
            <select
              className='form-select'
              value={examMode === 'preset' ? selectedPreset : '__custom__'}
              onChange={(e) => {
                const val = e.target.value
                if (val === '__custom__') {
                  setExamMode('custom')
                  setSelectedPreset('')
                  store.setCertificateCode('')
                } else if (val) {
                  setExamMode('preset')
                  setSelectedPreset(val)
                  const cat = certOptions.find(c => c.id === val)
                  if (cat) {
                    store.setCertificateCode(cat.id)
                    store.setExamName(cat.name)
                    store.setExamDate(cat.examDate)
                    resolveExamDate(cat.id).then(date => {
                      if (date) store.setExamDate(date)
                    })
                    if (cat.recommendedPreset) {
                      store.setCardSequence([...cat.recommendedPreset])
                    }
                  }
                } else {
                  setExamMode('preset')
                  setSelectedPreset('')
                  store.setCertificateCode('')
                  store.setExamName('')
                }
              }}
            >
              <optgroup label='━━ 预设考试 ━━'>
                {certsLoading ? (
                  <option disabled>加载中...</option>
                ) : (
                  certOptions.map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))
                )}
              </optgroup>
              <option value='__custom__'>+ 自定义输入</option>
            </select>
          </View>

          {/* 自定义考试名（仅自定义模式显示） */}
          {examMode === 'custom' && (
            <View className='form-group'>
              <Text className='form-label'>考试名称（自定义）</Text>
              <input
                className='form-input full'
                type='text'
                placeholder='输入考试名称，如：执业医师资格证'
                value={store.examName}
                onChange={(e) => store.setExamName(e.target.value)}
              />
            </View>
          )}

          {/* 日期 */}
          <View className='form-group'>
            <Text className='form-label'>考试日期</Text>
            <input
              className={`form-input full ${!store.examDate ? 'input-hint' : ''}`}
              type='date'
              value={store.examDate}
              onChange={(e) => store.setExamDate(e.target.value)}
              placeholder='请选择考试日期'
            />
            {!store.examDate && (
              <Text className='field-hint'>数据库暂无该考试的日期，请手动选择</Text>
            )}
          </View>

          {/* V1.1 目标人群 */}
          <View className='form-group'>
            <Text className='form-label'>目标人群</Text>
            <View className='audience-tags'>
              {TARGET_AUDIENCES.map(a => (
                <button
                  key={a.key}
                  className={`audience-tag ${store.targetAudience === a.key ? 'active' : ''}`}
                  onClick={() => store.setTargetAudience(a.key)}
                >
                  {a.label}
                </button>
              ))}
            </View>
            <input
              className={`form-input full ${audienceError && !store.targetAudience && !store.targetAudienceCustom ? 'input-error' : ''}`}
              type='text'
              placeholder='或自定义输入人群...'
              value={store.targetAudienceCustom}
              onFocus={() => { if (store.targetAudience) store.setTargetAudience(''); setAudienceError(false) }}
              onChange={(e) => { store.setTargetAudienceCustom(e.target.value); setAudienceError(false) }}
            />
            {audienceError && !store.targetAudience && !store.targetAudienceCustom && (
              <Text className='field-error'>请选择或输入目标人群</Text>
            )}
          </View>

          {/* V1.1 主题方向 */}
          <View className='form-group'>
            <Text className='form-label'>主题方向</Text>
            <select
              className={`form-select full ${themeError && !store.theme && !store.themeCustom ? 'input-error' : ''}`}
              value={store.theme}
              onChange={(e) => { store.setTheme(e.target.value); setThemeError(false) }}
            >
              {THEME_PRESETS.map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <input
              className={`form-input full ${themeError && !store.theme && !store.themeCustom ? 'input-error' : ''}`}
              type='text'
              placeholder='或自由输入主题方向...'
              value={store.themeCustom}
              onFocus={() => { if (store.theme) store.setTheme('') }}
              onChange={(e) => { store.setThemeCustom(e.target.value); setThemeError(false) }}
            />
            {themeError && !store.theme && !store.themeCustom && (
              <Text className='field-error'>请选择或输入主题</Text>
            )}
          </View>

          {/* 卡片编排 */}
          <View className='card-arranger'>
            <View className='card-arranger-title'>
              <Text>卡片编排（拖拽排序）</Text>
            </View>
            <View className='preset-btns'>
              <button className='btn-add-card' onClick={() => store.applyPreset(6)}>6 张标准</button>
              <button className='btn-add-card' onClick={() => store.applyPreset(5)}>5 张精简</button>
              <button className='btn-add-card' onClick={() => store.applyPreset(7)}>7 张含资料</button>
              <button className='btn-add-card' onClick={() => store.setCardSequence([...PRESET_PLAN_TYPE])}>📅 计划型</button>
              <button className='btn-add-card' onClick={() => store.setCardSequence([...PRESET_KNOWLEDGE_TYPE])}>📚 知识型</button>
            </View>
            <View className='card-chip-list'>
              {store.cardSequence.map((type, i) => (
                <div
                  key={i}
                  className='card-chip'
                  draggable
                  onDragStart={() => { dragSrcRef.current = i }}
                  onDragOver={(ev: React.DragEvent) => ev.preventDefault()}
                  onDrop={(ev: React.DragEvent) => {
                    ev.preventDefault()
                    const targetIndex = i
                    if (dragSrcRef.current >= 0 && dragSrcRef.current !== targetIndex) {
                      store.reorderCards(dragSrcRef.current, targetIndex)
                    }
                    dragSrcRef.current = -1
                  }}
                >
                  <Text>{CARD_TYPE_LABELS[type] || type}</Text>
                  <button className='remove-chip' onClick={() => store.removeCard(i)}>×</button>
                </div>
              ))}
            </View>
            <View className='add-card-row'>
              <button className='btn-add-card' onClick={() => setShowAddCard(true)}>+ 添加卡片</button>
            </View>
          </View>

          {/* 风格 */}
          <View className='form-group'>
            <Text className='form-label'>卡片风格</Text>
            <View className='style-grid'>
              {STYLE_TOKENS.map(style => (
                <View
                  key={style.key}
                  className={`style-option ${store.currentStyle === style.key ? 'active' : ''}`}
                  onClick={() => store.setCurrentStyle(style.key)}
                >
                  <View
                    className='style-dot'
                    style={{
                      background: `linear-gradient(135deg, ${style.cssVars['--title-color']}, ${style.cssVars['--tag-bg']})`,
                    }}
                  />
                  <Text>{style.name}</Text>
                </View>
              ))}
            </View>
          </View>

          {/* 高级选项 */}
          <View>
            <button className='accordion-toggle' onClick={() => setAccordionOpen(!accordionOpen)}>
              <Text className='arrow' style={{ transform: accordionOpen ? 'rotate(90deg)' : '' }}>▶</Text>
              <Text>高级选项（素材库 / 槽位微调）</Text>
            </button>
            {accordionOpen && (
              <View className='accordion-body'>
                <View className='form-group'>
                  <Text className='form-label'>底板素材（可选）</Text>
                  <select className='form-select'>
                    <option value=''>纯 CSS 渲染（默认）</option>
                    <option>品牌蓝底-带logo</option>
                    <option>医学元素背景</option>
                  </select>
                </View>
              </View>
            )}
          </View>

          {/* 生成按钮 */}
          <button
            className='btn-generate'
            disabled={store.isGenerating}
            onClick={handleGenerate}
          >
            ✨ 生成内容
          </button>
        </View>
      </View>

      {/* ===== 右栏：预览区 ===== */}
      <View className='ea-preview'>
        <View className='preview-header'>
          <Text className='preview-title'>卡片预览</Text>
          <View className='preview-toolbar'>
            <button
              className='btn'
              disabled={exporting}
              onClick={async () => {
                setExporting(true)
                setToastMsg(' 正在导出全部卡片...')
                await exportAll({
                  filenamePrefix: '备考卡片',
                  onProgress: (cur, total) => setToastMsg(`📥 正在导出... ${cur}/${total}`),
                })
                setToastMsg('✅ 导出完成')
                setTimeout(() => setToastMsg(''), 2000)
                setExporting(false)
              }}
            >📥 导出全部 PNG</button>
            <button
              className='btn'
              disabled={exporting || !store.isGenerated}
              onClick={async () => {
                const idx = parseInt(prompt('请输入要导出的卡片序号（1-' + store.cardSequence.length + '）', '1') ?? '0', 10)
                if (idx >= 1 && idx <= store.cardSequence.length) {
                  setExporting(true)
                  setToastMsg('正在导出...')
                  await exportSingle(idx - 1, `备考卡片_${idx}`)
                  setToastMsg('导出完成')
                  setTimeout(() => setToastMsg(''), 2000)
                  setExporting(false)
                }
              }}
            >📄 导出单张</button>
            <button
              className='btn'
              disabled={exporting}
              onClick={async () => {
                setExporting(true)
                setToastMsg('正在分层导出...')
                await exportLayered({
                  filenamePrefix: '备考卡片',
                  onProgress: (cur, total) => setToastMsg(`正在分层导出... ${cur}/${total}`),
                })
                setToastMsg('✅ 分层导出完成（每卡 3 层透明 PNG）')
                setTimeout(() => setToastMsg(''), 2000)
                setExporting(false)
              }}
            >分层导出</button>
          </View>
        </View>
        <View className='card-grid'>
          {!store.isGenerated ? (
            // 骨架占位
            store.cardSequence.map((_type, i) => (
              <View key={i} className='card-preview skeleton' {...{ 'data-card-index': i } as any} style={{
                borderRadius: styleVars['--card-radius'],
              } as React.CSSProperties}
              >
                <Text className='skeleton-placeholder'>占位</Text>
              </View>
            ))
          ) : (
            // 真实预览
            store.cardSequence.map((_, i) => {
              const card = store.getCurrentCard(i)
              if (!card) return null
              const hasVersions = store.cardVersions[i] && store.cardVersions[i].length > 1
              const currentVer = store.activeVersions[i] ?? 0
              return renderCardPreview(card, i, hasVersions, currentVer)
            })
          )}
        </View>
      </View>

      {/* ===== 确认生成 Dialog ===== */}
      {showConfirm && (
        <View className='dialog-overlay' onClick={(e) => { if (e.target === e.currentTarget) setShowConfirm(false) }}>
          <View className='dialog'>
            <Text className='dialog-title'>确认生成内容</Text>
            <View className='dialog-info'>
              <View className='info-row'><Text className='info-label'>考试</Text><Text className='info-value'>{store.examName || '（AI 推断）'}</Text></View>
              <View className='info-row'><Text className='info-label'>考试日期</Text><Text className='info-value'>{store.examDate || '（AI 推断）'}</Text></View>
              <View className='info-row'><Text className='info-label'>倒计时</Text><Text className='info-value'>{getCountdown(store.examDate)}</Text></View>
              <View className='info-row'><Text className='info-label'>卡片数量</Text><Text className='info-value'>{store.cardSequence.length} 张</Text></View>
              <View className='info-row'><Text className='info-label'>卡片序列</Text><Text className='info-value'>{store.cardSequence.map(t => CARD_TYPE_LABELS[t] || t).join(' → ')}</Text></View>
              <View className='info-row'><Text className='info-label'>风格</Text><Text className='info-value'>{STYLE_TOKENS.find(s => s.key === store.currentStyle)?.name ?? store.currentStyle}</Text></View>
              <View className='info-row'><Text className='info-label'>目标人群</Text><Text className={`info-value ${!store.targetAudience && !store.targetAudienceCustom ? 'info-warn' : ''}`}>{store.targetAudience || store.targetAudienceCustom || '（未填写）⚠️'}</Text></View>
              <View className='info-row'><Text className='info-label'>主题</Text><Text className='info-value'>{store.theme || store.themeCustom || '（未填写）⚠️'}</Text></View>
            </View>
            <Text className='warn-text'>⚠️ 如果日期或科目不对，请关闭后返回修改</Text>
            <View className='btn-row'>
              <button className='btn-cancel' onClick={() => setShowConfirm(false)}>返回修改</button>
              <button className='btn-confirm' onClick={startGenerate}>确认，开始生成</button>
            </View>
          </View>
        </View>
      )}

      {/* ===== 生成进度遮罩 ===== */}
      {store.isGenerating && (
        <View className='progress-overlay'>
          <View className='progress-steps'>
            {store.progressSteps.map(step => (
              <View key={step.id} className={`progress-step ${step.status}`}>
                <View className='step-icon'><Text>{step.id}</Text></View>
                <Text>{step.label}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {/* ===== 文本审核 Dialog ===== */}
      {store.isReviewing && store.pendingContent && (
        <View className='review-overlay'>
          <View className='review-dialog'>
            <View className='review-header'>
              <View className='review-header-left'>
                <Text className='review-title'>内容审核</Text>
                <View className='review-desc'>
                  <Text>请检查以下文案是否存在敏感词或重复内容</Text>
                  {store.reviewModifications.length > 0 && (
                    <View className='mod-count'>已修改 {store.reviewModifications.length} 次</View>
                  )}
                </View>
              </View>
              <button
                className='btn-copy-all'
                onClick={() => {
                  const allText = store.pendingContent
                    ? store.pendingContent.cards.map((c, i) => `【第${i + 1}张 · ${CARD_TYPE_LABELS[c.type] || c.type}】\n${getCardPlainText(c)}`).join('\n\n')
                    : ''
                  copyToClipboard(allText)
                }}
              >
                复制全文
              </button>
            </View>
            <View className='review-body'>
              {renderReviewCards()}
            </View>
            <View className='review-footer'>
              <View className='review-feedback-row'>
                <View className='review-problem-type'>
                  <button
                    className={`btn-problem-type ${reviewProblemType === 'sensitive' ? 'active' : ''}`}
                    onClick={() => setReviewProblemType('sensitive')}
                  >
                    敏感词
                  </button>
                  <button
                    className={`btn-problem-type ${reviewProblemType === 'duplicate' ? 'active' : ''}`}
                    onClick={() => setReviewProblemType('duplicate')}
                  >
                    查重
                  </button>
                </View>
                <textarea
                  className='review-feedback-input'
                  placeholder={reviewProblemType === 'sensitive' ? '请说明哪些是敏感词，例如：标题中的「上岸」是敏感词，需要替换...' : '请说明哪部分内容重复了，例如：封面标题与上一篇文章标题重复，需要改写...'}
                  value={reviewFeedback}
                  onChange={(e) => setReviewFeedback(e.target.value)}
                />
              </View>
              <View className='review-btn-row'>
                <button
                  className='btn-revert'
                  disabled={store.reviewModifications.length === 0}
                  onClick={revertToOriginal}
                >
                  ↩ 回退到初始版本
                </button>
                <View style={{ flex: 1 }} />
                <button
                  className='btn-submit-mod'
                  disabled={!reviewFeedback.trim()}
                  onClick={submitReviewModification}
                >
                  提交修改意见
                </button>
                <button className='btn-approve' onClick={approveReview}>
                  确认无误，下一步
                </button>
              </View>
            </View>
          </View>
        </View>
      )}

      {/* ===== 单卡重写 Dialog ===== */}
      {showRewrite && (
        <View className='dialog-overlay' onClick={(e) => { if (e.target === e.currentTarget) setShowRewrite(false) }}>
          <View className='dialog'>
            <Text className='dialog-title'>重写此卡片</Text>
            <Text className='dialog-desc'>请描述修改意见，AI 将在此基础上修改卡片内容。</Text>
            <textarea
              className='rewrite-feedback-input'
              placeholder='例如：加一些周末复习建议；日期需要从 6 月 12 日开始；科目列表加上题型说明...'
              value={rewriteFeedback}
              onChange={(e) => setRewriteFeedback(e.target.value)}
              rows={4}
            />
            <View className='btn-row'>
              <button className='btn-cancel' onClick={() => setShowRewrite(false)}>取消</button>
              <button className='btn-confirm' onClick={submitRewrite} disabled={!rewriteFeedback.trim()}>重写此卡</button>
            </View>
          </View>
        </View>
      )}

      {/* ===== 添加卡片 Dialog ===== */}
      {showAddCard && (
        <View className='dialog-overlay' onClick={(e) => { if (e.target === e.currentTarget) setShowAddCard(false) }}>
          <View className='dialog'>
            <Text className='dialog-title'>选择卡片类型</Text>
            <View className='add-card-grid'>
              {CARD_TYPE_OPTIONS.map(opt => (
                <View
                  key={opt.key}
                  className='add-card-option'
                  onClick={() => { store.addCard(opt.key); setShowAddCard(false) }}
                >
                  <Text>{opt.label}</Text>
                </View>
              ))}
            </View>
            <View className='btn-row'>
              <button className='btn-cancel' onClick={() => setShowAddCard(false)}>取消</button>
            </View>
          </View>
        </View>
      )}
    </View>
  )
}
