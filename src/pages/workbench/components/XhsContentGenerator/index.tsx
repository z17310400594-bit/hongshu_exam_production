import { Picker, View, Text } from '@tarojs/components'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useCertPresets } from '@/hooks/useCertPresets'
import { copyToClipboard } from '@/utils/clipboard'
import {
  fetchXhsChapters,
  generateXhsContent,
  type XhsAngleType,
  type XhsChapterOption,
  type XhsCtaType,
  type XhsDensity,
  type XhsGeneratePayload,
  type XhsGeneratedData,
  type XhsSourceMode,
} from '@/services/xhsContentApi'
import './index.scss'

const MAX_CUSTOM_TEXT = 3000

const ANGLES: Array<{ value: XhsAngleType; label: string }> = [
  { value: '错因诊断', label: '错因诊断：做题总错、学了但不会用' },
  { value: '口诀记忆', label: '口诀记忆：背了就忘、条目多' },
  { value: '避坑纠偏', label: '避坑纠偏：学习方法错、复盘无效' },
  { value: '阶段补救', label: '阶段补救：学到一半乱了、进度崩了' },
]

const CTA_TYPES: Array<{ value: XhsCtaType; label: string }> = [
  { value: '收藏+评论卡点', label: '收藏 + 评论卡点' },
  { value: '收藏复习', label: '收藏复习' },
  { value: '评论下一篇', label: '评论下一篇' },
  { value: '评论补救', label: '评论“补救”' },
]

const DENSITIES: Array<{ value: XhsDensity; label: string }> = [
  { value: '短平快', label: '短平快：4-6 张，少字强钩子' },
  { value: '信息稍密', label: '信息稍密：5-7 张，解释更多' },
]

function resolveChapterCertificateCode(certId: string, certName = ''): string {
  const joined = `${certId} ${certName}`.toLowerCase()
  if (joined.includes('pharmacist') || joined.includes('药师')) return 'pharmacist_licensed'
  return certId || 'pharmacist_licensed'
}

function formatPublicDraft(data: XhsGeneratedData, selectedTitleIndex: number): string {
  const ext = data.external
  const selectedTitle = ext.title_candidates.find(item => item.index === selectedTitleIndex)?.title
    ?? ext.title_candidates[0]?.title
    ?? ''
  const cards = ext.cards
    .map(card => `【第${card.card_no}张】${card.title}\n${card.body}`)
    .join('\n\n')
  return [
    `标题：${selectedTitle}`,
    `封面：${ext.cover_copy}`,
    '',
    cards,
    '',
    '正文：',
    ext.caption,
    '',
    ext.hashtags.join(' '),
    '',
    `CTA：${ext.cta}`,
    `今日小动作：${ext.today_action}`,
  ].join('\n')
}

function formatFullDraft(data: XhsGeneratedData, selectedTitleIndex: number, payload: XhsGeneratePayload): string {
  const ext = data.external
  const lines = [
    '【输入摘要】',
    `来源：${payload.source_mode === 'database' ? '数据库章节' : '自定义粘贴'}`,
    `知识点：${payload.knowledge_keyword || '未填写'}`,
    `内容角度：${payload.angle_type}`,
    `CTA：${payload.cta_type}`,
    `密度：${payload.density}`,
    '',
    '【原文依据】',
    ...data.internal.source_basis.map(item => `- ${item.source}：${item.quote}`),
    '',
    '【标题候选】',
    ...ext.title_candidates.map(item => `${item.index === selectedTitleIndex ? '✓ ' : ''}${item.index + 1}. ${item.title}（${item.style}）`),
    '',
    '【封面】',
    ext.cover_copy,
    '',
    '【卡片脚本】',
    ...ext.cards.map(card => `第${card.card_no}张｜${card.title}\n${card.body}\n版式建议：${card.layout_hint}`),
    '',
    '【正文 Caption】',
    ext.caption,
    '',
    '【话题标签】',
    ext.hashtags.join(' '),
    '',
    '【CTA】',
    ext.cta,
    '',
    '【今日小动作】',
    ext.today_action,
    '',
    '【风险提示】',
    ...data.internal.risk_notes.map(note => `- ${note}`),
    '',
    '【下一篇选题】',
    ...data.next_topics.map(topic => `- ${topic.title}｜${topic.angle_type}：${topic.reason}`),
  ]
  return lines.join('\n')
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return '请求失败，请稍后重试'
}

export default function XhsContentGenerator() {
  const { certOptions, loading: certsLoading, error: certsError } = useCertPresets()
  const [sourceMode, setSourceMode] = useState<XhsSourceMode>('database')
  const [selectedCertId, setSelectedCertId] = useState('')
  const [chapters, setChapters] = useState<XhsChapterOption[]>([])
  const [chaptersLoading, setChaptersLoading] = useState(false)
  const [chaptersError, setChaptersError] = useState('')
  const [selectedChapterId, setSelectedChapterId] = useState('')
  const [chapterQuery, setChapterQuery] = useState('')
  const [customText, setCustomText] = useState('')
  const [knowledgeKeyword, setKnowledgeKeyword] = useState('')
  const [angleType, setAngleType] = useState<XhsAngleType>('错因诊断')
  const [ctaType, setCtaType] = useState<XhsCtaType>('收藏+评论卡点')
  const [density, setDensity] = useState<XhsDensity>('短平快')
  const [extraRequirement, setExtraRequirement] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [result, setResult] = useState<XhsGeneratedData | null>(null)
  const [rawOutput, setRawOutput] = useState('')
  const [resultError, setResultError] = useState('')
  const [selectedTitleIndex, setSelectedTitleIndex] = useState(0)
  const [lastPayload, setLastPayload] = useState<XhsGeneratePayload | null>(null)
  const [toast, setToast] = useState('')

  const selectedCert = useMemo(
    () => certOptions.find(item => item.id === selectedCertId),
    [certOptions, selectedCertId],
  )
  const certIndex = useMemo(() => Math.max(0, certOptions.findIndex(item => item.id === selectedCertId)), [certOptions, selectedCertId])

  useEffect(() => {
    if (!selectedCertId && certOptions.length > 0) {
      const pharmacist = certOptions.find(item => `${item.id} ${item.name}`.includes('药师'))
      setSelectedCertId((pharmacist ?? certOptions[0]).id)
    }
  }, [certOptions, selectedCertId])

  const chapterCertificateCode = useMemo(
    () => resolveChapterCertificateCode(selectedCertId, selectedCert?.name),
    [selectedCertId, selectedCert?.name],
  )

  const loadChapters = useCallback(async () => {
    setChaptersLoading(true)
    setChaptersError('')
    try {
      const response = await fetchXhsChapters({
        certificateCode: chapterCertificateCode,
        query: chapterQuery.trim(),
        limit: 80,
      })
      setChapters(response.items)
      if (response.items.length > 0 && !response.items.some(item => item.chapterId === selectedChapterId)) {
        setSelectedChapterId(response.items[0].chapterId)
      }
    } catch (error) {
      setChapters([])
      setChaptersError(getErrorMessage(error))
    } finally {
      setChaptersLoading(false)
    }
  }, [chapterCertificateCode, chapterQuery, selectedChapterId])

  useEffect(() => {
    if (selectedCertId) {
      loadChapters()
    }
  }, [loadChapters, selectedCertId])

  const selectedChapter = useMemo(
    () => chapters.find(item => item.chapterId === selectedChapterId),
    [chapters, selectedChapterId],
  )
  const chapterIndex = useMemo(
    () => Math.max(0, chapters.findIndex(item => item.chapterId === selectedChapterId)),
    [chapters, selectedChapterId],
  )
  const angleIndex = useMemo(() => Math.max(0, ANGLES.findIndex(item => item.value === angleType)), [angleType])
  const ctaIndex = useMemo(() => Math.max(0, CTA_TYPES.findIndex(item => item.value === ctaType)), [ctaType])
  const densityIndex = useMemo(() => Math.max(0, DENSITIES.findIndex(item => item.value === density)), [density])

  const payload = useMemo<XhsGeneratePayload>(() => ({
    source_mode: sourceMode,
    chapter_id: sourceMode === 'database' ? selectedChapterId : '',
    custom_text: sourceMode === 'custom_text' ? customText.trim() : '',
    knowledge_keyword: knowledgeKeyword.trim(),
    angle_type: angleType,
    target_user: '学了一段但做题总错',
    tone: '备考陪跑',
    density,
    cta_type: ctaType,
    extra_requirement: extraRequirement.trim(),
  }), [angleType, ctaType, customText, density, extraRequirement, knowledgeKeyword, selectedChapterId, sourceMode])

  const validationMessage = useMemo(() => {
    if (sourceMode === 'database' && !selectedChapterId) return '请先选择数据库章节/片段'
    if (sourceMode === 'custom_text' && !customText.trim()) return '请先粘贴自定义素材'
    if (sourceMode === 'custom_text' && customText.length > MAX_CUSTOM_TEXT) return '自定义素材最多 3000 字'
    return ''
  }, [customText, selectedChapterId, sourceMode])

  const showToast = useCallback((message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 1800)
  }, [])

  const submitGenerate = useCallback(async (request: XhsGeneratePayload, confirmOverwrite = false) => {
    if (validationMessage) {
      showToast(validationMessage)
      return
    }
    if (confirmOverwrite && result && !window.confirm('重新生成会覆盖当前内容，是否继续？')) return
    setIsGenerating(true)
    setResultError('')
    setRawOutput('')
    try {
      const response = await generateXhsContent(request)
      setLastPayload(request)
      setRawOutput(response.raw_output)
      if (!response.ok || !response.data) {
        setResult(null)
        setResultError(response.error?.message || '生成结果格式异常')
        showToast('格式异常，已展示原始结果')
        return
      }
      setResult(response.data)
      setSelectedTitleIndex(response.data.external.selected_title_index ?? 0)
      showToast('已生成内容')
    } catch (error) {
      setResultError(getErrorMessage(error))
      showToast('生成失败')
    } finally {
      setIsGenerating(false)
    }
  }, [result, showToast, validationMessage])

  const copyPublic = useCallback(async () => {
    if (!result) return
    await copyToClipboard(formatPublicDraft(result, selectedTitleIndex))
    showToast('已复制对外发布稿')
  }, [result, selectedTitleIndex, showToast])

  const copyFull = useCallback(async () => {
    if (!result || !lastPayload) return
    await copyToClipboard(formatFullDraft(result, selectedTitleIndex, lastPayload))
    showToast('已复制完整笔记包')
  }, [lastPayload, result, selectedTitleIndex, showToast])

  const copyRaw = useCallback(async () => {
    if (!rawOutput) return
    await copyToClipboard(rawOutput)
    showToast('已复制原始结果')
  }, [rawOutput, showToast])

  return (
    <View className='xhs-generator'>
      <View className='xhs-config'>
        <View className='xhs-config-head'>
          <Text className='xhs-panel-title'>生成配置</Text>
          <Text className='xhs-badge'>默认错因诊断</Text>
        </View>

        <View className='xhs-form'>
          <View className='xhs-field'>
            <Text className='xhs-label'>证书项目</Text>
            <Picker
              mode='selector'
              range={certOptions.map(option => option.name)}
              value={certIndex}
              disabled={certsLoading || certOptions.length === 0}
              onChange={(event) => {
                const next = certOptions[Number(event.detail.value)]
                if (next) setSelectedCertId(next.id)
              }}
            >
              <View className='xhs-picker-value'>{selectedCert?.name || '暂无证书项目'}</View>
            </Picker>
            {certsError ? <Text className='xhs-hint danger'>{certsError}</Text> : null}
          </View>

          <View className='xhs-field'>
            <Text className='xhs-label'>素材来源</Text>
            <View className='xhs-segmented'>
              <button
                className={sourceMode === 'database' ? 'active' : ''}
                onClick={() => setSourceMode('database')}
              >数据库章节</button>
              <button
                className={sourceMode === 'custom_text' ? 'active' : ''}
                onClick={() => setSourceMode('custom_text')}
              >自定义粘贴</button>
            </View>
          </View>

          {sourceMode === 'database' ? (
            <View className='xhs-field'>
              <Text className='xhs-label'>章节/片段</Text>
              <View className='xhs-inline'>
                <input
                  className='xhs-input'
                  type='text'
                  placeholder='可搜索标题、原文或资产编码'
                  value={chapterQuery}
                  onChange={(event) => setChapterQuery(event.target.value)}
                />
                <button className='xhs-button' disabled={chaptersLoading} onClick={loadChapters}>搜索</button>
              </View>
              <Picker
                mode='selector'
                range={chapters.map(item => `${item.assetTitle} / ${item.title}`)}
                value={chapterIndex}
                disabled={chaptersLoading || chapters.length === 0}
                onChange={(event) => {
                  const next = chapters[Number(event.detail.value)]
                  if (next) setSelectedChapterId(next.chapterId)
                }}
              >
                <View className='xhs-picker-value'>
                  {selectedChapter ? `${selectedChapter.assetTitle} / ${selectedChapter.title}` : '暂无章节/片段'}
                </View>
              </Picker>
              {selectedChapter ? (
                <Text className='xhs-hint'>
                  {selectedChapter.textPreview || '无预览'}（{selectedChapter.textLength} 字；超过 3000 字后端会截断）
                </Text>
              ) : null}
              {chaptersError ? <Text className='xhs-hint danger'>{chaptersError}</Text> : null}
            </View>
          ) : (
            <View className='xhs-field'>
              <Text className='xhs-label'>自定义素材</Text>
              <textarea
                className='xhs-textarea'
                value={customText}
                placeholder='粘贴外部考点、教材原文或笔记，最多 3000 字'
                onChange={(event) => setCustomText(event.target.value)}
              />
              <View className={`xhs-counter ${customText.length > MAX_CUSTOM_TEXT ? 'over' : ''}`}>
                <Text>建议只粘贴和本篇相关的素材</Text>
                <Text>{customText.length}/{MAX_CUSTOM_TEXT}</Text>
              </View>
            </View>
          )}

          <View className='xhs-field'>
            <Text className='xhs-label'>知识点关键词（可选）</Text>
            <input
              className='xhs-input'
              type='text'
              placeholder='例如：麻黄、问寒热、行政复议'
              value={knowledgeKeyword}
              onChange={(event) => setKnowledgeKeyword(event.target.value)}
            />
            <Text className='xhs-hint'>不填时基于整段素材生成，内容可能更泛。</Text>
          </View>

          <View className='xhs-field'>
            <Text className='xhs-label'>内容角度</Text>
            <Picker
              mode='selector'
              range={ANGLES.map(item => item.label)}
              value={angleIndex}
              onChange={(event) => {
                const next = ANGLES[Number(event.detail.value)]
                if (next) setAngleType(next.value)
              }}
            >
              <View className='xhs-picker-value'>{ANGLES[angleIndex]?.label}</View>
            </Picker>
          </View>

          <View className='xhs-field'>
            <Text className='xhs-label'>CTA</Text>
            <Picker
              mode='selector'
              range={CTA_TYPES.map(item => item.label)}
              value={ctaIndex}
              onChange={(event) => {
                const next = CTA_TYPES[Number(event.detail.value)]
                if (next) setCtaType(next.value)
              }}
            >
              <View className='xhs-picker-value'>{CTA_TYPES[ctaIndex]?.label}</View>
            </Picker>
          </View>

          <View className='xhs-field'>
            <Text className='xhs-label'>卡片密度</Text>
            <Picker
              mode='selector'
              range={DENSITIES.map(item => item.label)}
              value={densityIndex}
              onChange={(event) => {
                const next = DENSITIES[Number(event.detail.value)]
                if (next) setDensity(next.value)
              }}
            >
              <View className='xhs-picker-value'>{DENSITIES[densityIndex]?.label}</View>
            </Picker>
          </View>

          <View className='xhs-field'>
            <Text className='xhs-label'>补充要求（可选）</Text>
            <textarea
              className='xhs-textarea small'
              placeholder='例如：标题轻松一点，不要太焦虑；专业内容只做信任背书。'
              value={extraRequirement}
              onChange={(event) => setExtraRequirement(event.target.value)}
            />
          </View>

          {validationMessage ? <Text className='xhs-hint danger'>{validationMessage}</Text> : null}
          <button
            className='xhs-generate'
            disabled={isGenerating || Boolean(validationMessage)}
            onClick={() => submitGenerate(payload, false)}
          >
            {isGenerating ? '生成中，请稍等...' : '生成内容'}
          </button>
        </View>
      </View>

      <View className='xhs-result'>
        <View className='xhs-result-head'>
          <Text className='xhs-panel-title'>生成结果</Text>
          <View className='xhs-actions'>
            <button className='xhs-button ghost' disabled={!result} onClick={copyPublic}>复制对外发布稿</button>
            <button className='xhs-button ghost' disabled={!result} onClick={copyFull}>复制完整笔记包</button>
            <button className='xhs-button' disabled={!lastPayload || isGenerating} onClick={() => lastPayload && submitGenerate(lastPayload, true)}>重新生成</button>
          </View>
        </View>

        <View className='xhs-result-body'>
          {!result && !resultError ? (
            <View className='xhs-empty'>
              <Text className='xhs-empty-title'>还没有生成内容</Text>
              <Text>选择素材来源和角度后，生成一篇小红书备考陪跑笔记。</Text>
            </View>
          ) : null}

          {resultError ? (
            <View className='xhs-error-panel'>
              <Text className='xhs-error-title'>生成结果异常</Text>
              <Text className='xhs-error-text'>{resultError}</Text>
              {rawOutput ? (
                <>
                  <button className='xhs-button' onClick={copyRaw}>复制原始结果</button>
                  <Text className='xhs-raw'>{rawOutput}</Text>
                </>
              ) : null}
            </View>
          ) : null}

          {result ? (
            <View className='xhs-sections'>
              <View className='xhs-section'>
                <Text className='xhs-section-title'>原文依据</Text>
                {result.internal.source_basis.slice(0, 5).map((item, index) => (
                  <View key={`${item.source}-${index}`} className='xhs-text-block'>
                    <Text className='xhs-source-title'>{item.source}</Text>
                    <Text>{item.quote}</Text>
                  </View>
                ))}
              </View>

              <View className='xhs-section'>
                <Text className='xhs-section-title'>标题候选（3 选 1）</Text>
                <View className='xhs-title-list'>
                  {result.external.title_candidates.map(item => (
                    <View
                      key={item.index}
                      className={`xhs-title-option ${item.index === selectedTitleIndex ? 'active' : ''}`}
                      onClick={() => setSelectedTitleIndex(item.index)}
                    >
                      <Text className='xhs-title-text'>{item.title}</Text>
                      <Text className='xhs-title-style'>{item.style}</Text>
                    </View>
                  ))}
                </View>
              </View>

              <View className='xhs-section'>
                <Text className='xhs-section-title'>封面文案</Text>
                <View className='xhs-cover'>{result.external.cover_copy}</View>
              </View>

              <View className='xhs-section'>
                <Text className='xhs-section-title'>卡片脚本</Text>
                <View className='xhs-card-list'>
                  {result.external.cards.map(card => (
                    <View key={card.card_no} className='xhs-card'>
                      <View className='xhs-card-top'>
                        <Text className='xhs-card-no'>{card.card_no}</Text>
                        <Text className='xhs-card-title'>{card.title}</Text>
                      </View>
                      <Text className='xhs-card-body'>{card.body}</Text>
                      <Text className='xhs-layout-hint'>版式建议：{card.layout_hint}</Text>
                    </View>
                  ))}
                </View>
              </View>

              <View className='xhs-section'>
                <Text className='xhs-section-title'>正文 Caption</Text>
                <Text className='xhs-text-block'>{result.external.caption}</Text>
              </View>

              <View className='xhs-section'>
                <Text className='xhs-section-title'>话题标签</Text>
                <View className='xhs-tags'>
                  {result.external.hashtags.map(tag => <Text key={tag} className='xhs-tag'>{tag}</Text>)}
                </View>
              </View>

              <View className='xhs-section'>
                <Text className='xhs-section-title'>CTA</Text>
                <Text className='xhs-text-block'>{result.external.cta}</Text>
              </View>

              <View className='xhs-section'>
                <Text className='xhs-section-title'>今日小动作</Text>
                <Text className='xhs-text-block'>{result.external.today_action}</Text>
              </View>

              <View className='xhs-section'>
                <Text className='xhs-section-title'>风险提示</Text>
                {result.internal.risk_notes.map((note, index) => (
                  <Text key={`${note}-${index}`} className='xhs-warning'>{note}</Text>
                ))}
              </View>

              <View className='xhs-section'>
                <Text className='xhs-section-title'>下一篇延展</Text>
                {result.next_topics.map((topic, index) => (
                  <View key={`${topic.title}-${index}`} className='xhs-text-block'>
                    <Text className='xhs-source-title'>{topic.title}</Text>
                    <Text>{topic.angle_type}：{topic.reason}</Text>
                  </View>
                ))}
              </View>
            </View>
          ) : null}
        </View>
      </View>

      <View className={`xhs-toast ${toast ? 'show' : ''}`}>{toast}</View>
    </View>
  )
}
