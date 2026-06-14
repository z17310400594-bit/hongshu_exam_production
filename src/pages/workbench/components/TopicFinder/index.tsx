import { View, Text } from '@tarojs/components'
import { useState, useCallback, useRef } from 'react'
import { useTopicFinderStore } from '@/store/topicFinderStore'
import { EXAM_CATEGORIES } from '@/constants/exam-categories'
import { ConfidenceMeta, SourceMeta } from '@/types/topic-finder'
import { copyToClipboard } from '@/utils/clipboard'
import './index.scss'

export default function TopicFinder() {
  const {
    currentCategory, keyword, topics, isLoading,
    daysRemaining, currentPhase, historyRecords, lastUpdate,
    setCategory, setKeyword, triggerAnalysis,
    uploadHistoryFile, downloadTemplate, clearHistory,
  } = useTopicFinderStore()

  const [showDataDialog, setShowDataDialog] = useState(false)
  const [expandedTopics, setExpandedTopics] = useState<Set<number>>(new Set())
  const [toastMsg, setToastMsg] = useState('')
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const recordCount = historyRecords.length

  // Toast 显示
  const showToast = useCallback((msg: string) => {
    setToastMsg(msg)
    setTimeout(() => setToastMsg(''), 2000)
  }, [])

  // 展开/收起分析依据
  const toggleReasons = useCallback((idx: number) => {
    setExpandedTopics(prev => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }, [])

  // 复制选题
  const copyTopic = useCallback(async (title: string) => {
    try {
      await copyToClipboard(title.replace(/<[^>]*>/g, ''))
      showToast('✅ 选题已复制到剪贴板')
    } catch {
      showToast('❌ 复制失败，请手动复制')
    }
  }, [showToast])

  // 文件上传
  const handleFileUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.name.endsWith('.md')) {
      showToast('❌ 仅支持 .md 格式文件')
      return
    }
    if (file.size > 51200) {
      showToast('❌ 文件过大，请控制在 50KB 以内')
      return
    }

    const reader = new FileReader()
    reader.onload = (ev) => {
      const content = ev.target?.result as string
      const result = uploadHistoryFile(content)
      if (result.errors.length > 0) {
        showToast('⚠️ ' + result.errors[0])
      } else {
        showToast(`✅ 已解析 ${result.count} 条历史选题数据，纳入分析`)
        triggerAnalysis()
      }
    }
    reader.readAsText(file, 'utf-8')
    // reset input
    e.target.value = ''
  }, [uploadHistoryFile, showToast, triggerAnalysis])

  // 切换类目
  const handleCategoryChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setCategory(e.target.value)
  }, [setCategory])

  return (
    <View className='topic-finder'>
      {/* Toast */}
      {toastMsg && <View className='toast show'>{toastMsg}</View>}

      {/* 顶部标题栏 */}
      <View className='tf-header'>
        <Text className='tf-title'>📋 小红书选题分析</Text>
        <View className='tf-header-actions'>
          <button className='btn' onClick={() => setShowDataDialog(true)}>📂 数据管理</button>
        </View>
      </View>

      {/* 控制栏 */}
      <View className='tf-control-bar'>
        <View className='form-group'>
          <Text className='form-label'>考试类目</Text>
          <select className='form-select' value={currentCategory} onChange={handleCategoryChange}>
            {EXAM_CATEGORIES.map(cat => (
              <option key={cat.id} value={cat.id}>{cat.name}</option>
            ))}
          </select>
        </View>
        <View className='form-group'>
          <Text className='form-label'>细分方向（可选）</Text>
          <input
            className='form-input'
            type='text'
            placeholder='如：心血管系统'
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onBlur={() => keyword && triggerAnalysis()}
            onKeyDown={(e) => { if (e.key === 'Enter') triggerAnalysis() }}
          />
        </View>
        <button
          className='btn btn-primary btn-refresh'
          onClick={triggerAnalysis}
          disabled={isLoading}
        >
          🔄 刷新分析
        </button>
      </View>

      {/* 状态条 */}
      <View className='tf-status-bar'>
        <View className='status-phase'>
          <View className='phase-dot' />
          <Text>{currentPhase}</Text>
        </View>
        <View className='status-divider' />
        <Text className='status-days'>
          距考试 <Text className='status-days-num'>{daysRemaining}</Text> 天
        </Text>
        <View className='status-divider' />
        <View className={`data-badge ${recordCount > 0 ? 'has-data' : ''}`}>
          {recordCount > 0 ? `📊 历史数据 ${recordCount} 条` : '📊 暂无历史数据'}
        </View>
      </View>

      {/* Loading / 选题列表 */}
      {isLoading ? (
        <View className='tf-skeleton-list'>
          {[1, 2, 3, 4].map(i => (
            <View key={i} className='tf-skeleton-card'>
              <View className='skeleton-line short' />
              <View className='skeleton-line' />
              <View className='skeleton-line medium' />
            </View>
          ))}
        </View>
      ) : topics.length === 0 ? (
        <View className='tf-empty'>
          <Text className='tf-empty-icon'>📭</Text>
          <Text className='tf-empty-text'>选择考试类目后自动分析</Text>
        </View>
      ) : (
        <View className='tf-topic-list'>
          {topics.map((topic, i) => {
            const c = ConfidenceMeta[topic.confidence]
            const isExpanded = expandedTopics.has(i)
            return (
              <View key={i} className={`topic-card confidence-${topic.confidence}`}>
                <View className='topic-card-header'>
                  <Text className='topic-rank'>{i + 1}</Text>
                  <View className='topic-body'>
                    <View className='topic-title-row'>
                      <Text className='topic-title'>{topic.title}</Text>
                      <View className={`confidence-badge ${c.cls}`}>{c.text}</View>
                    </View>
                    <button
                      className={`btn-expand ${isExpanded ? 'open' : ''}`}
                      onClick={() => toggleReasons(i)}
                    >
                      <Text className='arrow-expand'>▾</Text>
                      {isExpanded ? '收起分析' : '展开分析'}
                    </button>
                  </View>
                  <View className='topic-actions'>
                    <button className='btn-icon' onClick={() => copyTopic(topic.title)} title='复制选题'>📋</button>
                  </View>
                </View>
                {isExpanded && (
                  <View className='reasons-container show'>
                    <Text className='reasons-title'>分析依据</Text>
                    {topic.reasons.map((r, j) => (
                      <View key={j} className='reason-item'>
                        <View className={`reason-source ${SourceMeta[r.source].cls}`}>
                          {SourceMeta[r.source].text}
                        </View>
                        <Text className='reason-text'>{r.text}</Text>
                      </View>
                    ))}
                  </View>
                )}
              </View>
            )
          })}
        </View>
      )}

      {/* 底部栏 */}
      <View className='tf-bottom-bar'>
        <Text className='meta-text'>
          历史选题数据：<strong>{recordCount}</strong> 条 |
          上次更新：<Text>{lastUpdate || '—'}</Text>
        </Text>
        <button className='btn btn-text' onClick={() => setShowDataDialog(true)}>管理数据 →</button>
      </View>

      {/* 数据管理弹窗 */}
      {showDataDialog && (
        <View className='dialog-overlay' onClick={(e) => { if (e.target === e.currentTarget) setShowDataDialog(false) }}>
          <View className='dialog'>
            <Text className='dialog-title'>📂 历史选题数据管理</Text>
            <Text className='dialog-desc'>
              上传公司历史发布中互动表现好的笔记数据，系统会纳入选题分析。支持 Markdown（.md）格式。
            </Text>

            {/* 上传区 */}
            <View className='upload-zone' onClick={() => fileInputRef.current?.click()}>
              <Text className='upload-icon'>📁</Text>
              <Text className='upload-text'>点击此处上传 .md 文件，或拖拽到此处</Text>
              <Text className='upload-hint'>仅支持 .md 格式，单文件不超过 50KB</Text>
            </View>
            <input
              ref={fileInputRef}
              type='file'
              accept='.md'
              style={{ display: 'none' }}
              onChange={handleFileUpload}
            />

            <View className='dialog-btn-group'>
              <button className='btn' onClick={downloadTemplate}>📥 下载数据模板</button>
              <button className='btn' onClick={() => { clearHistory(); showToast('🗑 历史数据已清空') }}>🗑 清空历史数据</button>
            </View>

            {/* 数据预览 */}
            <Text className='dialog-subtitle'>已录入数据预览</Text>
            <View className='data-preview'>
              {recordCount === 0 ? (
                <View className='empty-state'>
                  <Text className='empty-icon'>📭</Text>
                  <Text>暂无历史选题数据</Text>
                  <Text className='empty-hint'>下载模板 → 按格式填写 → 上传文件</Text>
                </View>
              ) : (
                <table className='data-table'>
                  <thead>
                    <tr>
                      <th>类目</th>
                      <th>记录数</th>
                      <th>最后更新</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>{EXAM_CATEGORIES.find(c => c.id === currentCategory)?.name ?? currentCategory}</td>
                      <td>{recordCount} 条</td>
                      <td>{lastUpdate || '—'}</td>
                    </tr>
                  </tbody>
                </table>
              )}
            </View>

            <View className='btn-row'>
              <button className='btn-cancel' onClick={() => setShowDataDialog(false)}>关闭</button>
              <button
                className='btn-confirm'
                onClick={() => { setShowDataDialog(false); triggerAnalysis(); showToast('📊 数据已应用，正在重新分析') }}
              >
                应用并重新分析
              </button>
            </View>
          </View>
        </View>
      )}
    </View>
  )
}
