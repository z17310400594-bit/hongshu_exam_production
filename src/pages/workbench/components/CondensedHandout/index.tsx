import { View, Text } from '@tarojs/components'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  FALLBACK_CONDENSED_CHAPTERS,
  fetchCondensedChapterDetail,
  fetchCondensedChapters,
  getFallbackCondensedDetail,
  submitCondensedFeedback,
  type CondensedChapterDetail,
  type CondensedChapterListItem,
  type CondensedFeedbackStatus,
} from '@/services/condensedHandoutApi'
import './index.scss'

const FEEDBACK_OPTIONS: Array<{ value: CondensedFeedbackStatus; label: string }> = [
  { value: 'usable', label: '可用' },
  { value: 'needs_revision', label: '需修改' },
  { value: 'not_usable', label: '不可用' },
]

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return '请求失败，请稍后重试'
}

function statusLabel(status: string): string {
  if (status === 'ready') return '已生成'
  if (status === 'locked') return '未开放'
  return status
}

function feedbackLabel(status: CondensedFeedbackStatus | null): string {
  if (status === 'usable') return '可用'
  if (status === 'needs_revision') return '需修改'
  if (status === 'not_usable') return '不可用'
  return '待反馈'
}

function Tag({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'ok' | 'warn' | 'danger' | 'neutral' }) {
  return <Text className={`handout-tag ${tone}`}>{children}</Text>
}

function tagTone(value: string | null): 'ok' | 'warn' | 'danger' | 'neutral' {
  if (value === 'ready' || value === 'usable') return 'ok'
  if (value === 'locked' || value === 'not_usable') return 'danger'
  if (value === 'needs_revision' || value === null) return 'warn'
  return 'neutral'
}

export default function CondensedHandout() {
  const [chapters, setChapters] = useState<CondensedChapterListItem[]>(FALLBACK_CONDENSED_CHAPTERS)
  const [selectedCode, setSelectedCode] = useState('chapter_03')
  const [detail, setDetail] = useState<CondensedChapterDetail | null>(getFallbackCondensedDetail('chapter_03'))
  const [loading, setLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState('')
  const [feedbackStatus, setFeedbackStatus] = useState<CondensedFeedbackStatus>('usable')
  const [feedbackNote, setFeedbackNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [toast, setToast] = useState('')

  const selectedChapter = useMemo(
    () => chapters.find(chapter => chapter.chapterCode === selectedCode),
    [chapters, selectedCode],
  )

  const showToast = useCallback((message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 1600)
  }, [])

  const loadChapters = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const response = await fetchCondensedChapters()
      setChapters(response.chapters)
      const defaultChapter = response.chapters.find(chapter => chapter.chapterCode === 'chapter_03' && chapter.status !== 'locked')
        ?? response.chapters.find(chapter => chapter.status !== 'locked')
      if (defaultChapter) setSelectedCode(defaultChapter.chapterCode)
    } catch (err) {
      setChapters(FALLBACK_CONDENSED_CHAPTERS)
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadDetail = useCallback(async (chapterCode: string) => {
    setDetailLoading(true)
    setError('')
    try {
      const response = await fetchCondensedChapterDetail(chapterCode)
      setDetail(response)
      setFeedbackStatus(response.feedback.status ?? 'usable')
      setFeedbackNote(response.feedback.note ?? '')
    } catch (err) {
      setDetail(getFallbackCondensedDetail(chapterCode))
      setError(getErrorMessage(err))
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    loadChapters()
  }, [loadChapters])

  useEffect(() => {
    if (selectedCode) loadDetail(selectedCode)
  }, [loadDetail, selectedCode])

  const submitFeedback = useCallback(async () => {
    if (!detail || detail.status === 'locked') return
    setSubmitting(true)
    try {
      const response = await submitCondensedFeedback(detail.chapterCode, {
        status: feedbackStatus,
        note: feedbackNote.trim(),
      })
      setDetail(current => current ? { ...current, feedback: response.feedback } : current)
      setChapters(current => current.map(chapter => (
        chapter.chapterCode === detail.chapterCode
          ? { ...chapter, feedbackStatus: response.feedback.status }
          : chapter
      )))
      showToast('反馈已提交')
    } catch (err) {
      showToast(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }, [detail, feedbackNote, feedbackStatus, showToast])

  return (
    <View className='handout-page'>
      <View className='handout-chapters'>
        <View className='handout-pane-head'>
          <Text className='handout-pane-title'>西药一浓缩讲义</Text>
          <Text className='handout-pane-subtitle'>业务验证 MVP，仅查阅已生成样稿</Text>
        </View>
        <View className='handout-chapter-list'>
          {chapters.map(chapter => {
            const locked = chapter.status === 'locked'
            return (
              <View
                key={chapter.chapterCode}
                className={`handout-chapter ${selectedCode === chapter.chapterCode ? 'active' : ''} ${locked ? 'locked' : ''}`}
                onClick={() => {
                  if (!locked) setSelectedCode(chapter.chapterCode)
                }}
              >
                <Text className='handout-chapter-title'>{chapter.title}</Text>
                <Text className='handout-chapter-summary'>{chapter.summary}</Text>
                <View className='handout-tag-row'>
                  <Tag tone={tagTone(chapter.status)}>{statusLabel(chapter.status)}</Tag>
                  <Tag tone={tagTone(chapter.feedbackStatus)}>{feedbackLabel(chapter.feedbackStatus)}</Tag>
                </View>
              </View>
            )
          })}
          {!loading && chapters.length === 0 ? <Text className='handout-empty-text'>暂无章节</Text> : null}
        </View>
      </View>

      <View className='handout-content'>
        {error ? <View className='handout-error'>{error}</View> : null}
        {detailLoading || !detail ? (
          <View className='handout-loading'>{detailLoading ? '加载章节内容...' : '请选择章节'}</View>
        ) : (
          <>
            <View className='handout-header'>
              <View>
                <Text className='handout-title'>{detail.title}</Text>
                <Text className='handout-meta'>{selectedChapter?.summary || detail.summary}</Text>
              </View>
              <Tag tone='warn'>业务验证稿</Tag>
            </View>

            <View className='handout-detail-grid'>
              <View className='handout-article'>
                <Section title='章节正文摘要' items={detail.content.sourceSummary} />
                <Section title='浓缩讲义' items={detail.content.condensedBody} />
                <Section title='学习目标' items={detail.content.learningGoals} ordered />

                <View className='handout-section'>
                  <Text className='handout-section-title'>核心考点</Text>
                  <View className='handout-point-grid'>
                    {detail.content.corePoints.map(point => (
                      <View key={point.name} className='handout-point'>
                        <Text className='handout-point-name'>{point.name}</Text>
                        <Text className='handout-point-body'>{point.content}</Text>
                      </View>
                    ))}
                  </View>
                </View>

                <Section title='典型问法' items={detail.content.typicalQuestionPatterns} ordered />
                <Section title='待人工复核项' items={detail.content.reviewWarnings} tone='warn' ordered />
              </View>

              <View className='handout-side'>
                <SideCard title='来源'>
                  {detail.sources.map((source, index) => (
                    <View key={`${source.sourceTitle}-${source.page}-${index}`} className='handout-side-item'>
                      <Text className='handout-side-title'>{source.sourceTitle} / {source.page}</Text>
                      <Text className='handout-quote'>{source.quote}</Text>
                    </View>
                  ))}
                </SideCard>

                <SideCard title='真题佐证'>
                  {detail.examEvidence.map((item, index) => (
                    <View key={`${item.year}-${item.questionNo}-${index}`} className='handout-side-item'>
                      <Text className='handout-side-title'>{item.year} {item.questionNo || '题号待核'}</Text>
                      <Text className='handout-quote'>{item.summary}</Text>
                    </View>
                  ))}
                </SideCard>

                <SideCard title='业务反馈'>
                  <View className='handout-feedback-options'>
                    {FEEDBACK_OPTIONS.map(option => (
                      <button
                        key={option.value}
                        className={`handout-feedback-btn ${feedbackStatus === option.value ? 'active' : ''}`}
                        onClick={() => setFeedbackStatus(option.value)}
                      >
                        {option.label}
                      </button>
                    ))}
                  </View>
                  <textarea
                    className='handout-feedback-note'
                    value={feedbackNote}
                    placeholder='备注，例如：重点基本准确，但易混点还要补充。'
                    onChange={(event) => setFeedbackNote(event.target.value)}
                  />
                  <button className='handout-submit' disabled={submitting} onClick={submitFeedback}>
                    {submitting ? '提交中...' : '提交反馈'}
                  </button>
                </SideCard>
              </View>
            </View>
          </>
        )}
      </View>

      <View className={`handout-toast ${toast ? 'show' : ''}`}>{toast}</View>
    </View>
  )
}

function Section({
  title,
  items,
  ordered = false,
  tone = 'normal',
}: {
  title: string
  items: string[]
  ordered?: boolean
  tone?: 'normal' | 'warn'
}) {
  return (
    <View className={`handout-section ${tone}`}>
      <Text className='handout-section-title'>{title}</Text>
      <View className='handout-list'>
        {items.map((item, index) => (
          <View key={`${title}-${index}`} className='handout-list-item'>
            {ordered ? <Text className='handout-list-marker'>{index + 1}</Text> : null}
            <Text className='handout-list-text'>{item}</Text>
          </View>
        ))}
      </View>
    </View>
  )
}

function SideCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View className='handout-side-card'>
      <Text className='handout-side-head'>{title}</Text>
      <View className='handout-side-body'>{children}</View>
    </View>
  )
}
