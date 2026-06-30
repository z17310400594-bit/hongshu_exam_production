import { Button, ScrollView, Text, View } from '@tarojs/components'
import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '@/services/httpClient'
import {
  createV2BusinessFlowGeneration,
  fetchV2BusinessFlowSnapshot,
  type ScenarioResult,
  type V2BusinessFlowSnapshot,
} from '@/services/v2BusinessFlowApi'
import type {
  V2CertificateDetail,
  V2CertificateExamEventsResponse,
  V2EligibilityResponse,
  V2GenerationResponse,
  V2KnowledgeSearchResponse,
  V2QuestionBankResponse,
} from '@/types/api'
import './index.scss'

function StatusPill({ ok, text }: { ok: boolean; text: string }) {
  return <Text className={`v2-pill ${ok ? 'ok' : 'warn'}`}>{text}</Text>
}

function ErrorBlock<T>({ result }: { result: ScenarioResult<T> }) {
  if (result.status !== 'error') return null
  return (
    <View className='v2-error'>
      <Text>{result.error?.code ?? 'ERROR'}</Text>
      <Text>{result.error?.message ?? '请求失败'}</Text>
      {result.error?.requestId ? <Text>requestId: {result.error.requestId}</Text> : null}
    </View>
  )
}

function Card({ title, children, ok }: { title: string; children: React.ReactNode; ok: boolean }) {
  return (
    <View className='v2-card'>
      <View className='v2-card-head'>
        <Text className='v2-card-title'>{title}</Text>
        <StatusPill ok={ok} text={ok ? '已连接' : '需处理'} />
      </View>
      {children}
    </View>
  )
}

function DataLine({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <View className='v2-line'>
      <Text className='v2-line-label'>{label}</Text>
      <Text className='v2-line-value'>{value ?? '—'}</Text>
    </View>
  )
}

function CertificateCard({ result }: { result: ScenarioResult<V2CertificateDetail> }) {
  const cert = result.data
  return (
    <Card title='证书基础库' ok={result.status === 'ok'}>
      <ErrorBlock result={result} />
      {cert ? (
        <>
          <DataLine label='证书' value={`${cert.name}（${cert.code}）`} />
          <DataLine label='主管/考试机构' value={cert.examAuthority || cert.issuingAuthority} />
          <DataLine label='别名' value={cert.aliases.join('、')} />
        </>
      ) : null}
    </Card>
  )
}

function ExamCard({ result }: { result: ScenarioResult<V2CertificateExamEventsResponse> }) {
  const selectedEvent = result.data?.selectedEvent
  const writtenPhase = selectedEvent?.phases.find(phase => (phase.type ?? phase.phaseType) === 'written')
  return (
    <Card title='考试时间与阶段' ok={result.status === 'ok'}>
      <ErrorBlock result={result} />
      {selectedEvent ? (
        <>
          <DataLine label='考试事件' value={selectedEvent.eventCode ?? selectedEvent.code} />
          <DataLine label='年度/地区' value={`${selectedEvent.examYear} / ${selectedEvent.regionCode}`} />
          <DataLine label='笔试开始' value={writtenPhase?.startsOn} />
          <View className='v2-phase-list'>
            {selectedEvent.phases.map(phase => (
              <Text key={`${phase.phaseType ?? phase.type}-${phase.startsOn}`} className='v2-tag'>
                {phase.phaseType ?? phase.type}: {phase.startsOn}
              </Text>
            ))}
          </View>
        </>
      ) : null}
    </Card>
  )
}

function EligibilityCard({ title, result }: { title: string; result: ScenarioResult<V2EligibilityResponse> }) {
  const eligibility = result.data
  const isOk = result.status === 'ok' && eligibility?.decision !== 'insufficient_data'
  return (
    <Card title={title} ok={isOk}>
      <ErrorBlock result={result} />
      {eligibility ? (
        <>
          <DataLine label='判断' value={eligibility.decision} />
          <DataLine label='命中规则' value={eligibility.matchedRuleCode} />
          <DataLine label='原因' value={eligibility.reason} />
          <DataLine label='引用数量' value={eligibility.citations.length} />
        </>
      ) : null}
    </Card>
  )
}

function KnowledgeCard({ result }: { result: ScenarioResult<V2KnowledgeSearchResponse> }) {
  const first = result.data?.items[0]
  return (
    <Card title='知识检索与引用' ok={result.status === 'ok' && Boolean(first)}>
      <ErrorBlock result={result} />
      {first ? (
        <>
          <DataLine label='命中文档' value={`${first.assetTitle}（${first.assetCode}）`} />
          <DataLine label='片段' value={first.fragmentCode} />
          <DataLine label='知识点' value={first.knowledgePointCodes.join('、')} />
          <Text className='v2-snippet'>{first.content}</Text>
        </>
      ) : null}
    </Card>
  )
}

function PermissionCard({ result }: { result: ScenarioResult<V2KnowledgeSearchResponse> }) {
  const denied = result.status === 'error' && result.error?.status === 403
  return (
    <Card title='权限拒绝展示' ok={denied}>
      {denied ? (
        <View className='v2-safe-denied'>
          <Text>运营组织访问内部资料被拒绝。</Text>
          <Text>页面只显示错误码，不展示资料标题和正文。</Text>
          <Text>{result.error?.code}</Text>
        </View>
      ) : (
        <>
          <ErrorBlock result={result} />
          <DataLine label='状态' value='未触发预期的 403 权限保护' />
        </>
      )}
    </Card>
  )
}

function QuestionCard({ result }: { result: ScenarioResult<V2QuestionBankResponse> }) {
  const paper = result.data?.paper
  const firstQuestion = result.data?.questions[0]
  return (
    <Card title='题库样例' ok={result.status === 'ok' && Boolean(firstQuestion)}>
      <ErrorBlock result={result} />
      {paper ? (
        <>
          <DataLine label='试卷' value={`${paper.title}（${paper.code}）`} />
          <DataLine label='题量' value={result.data?.stats.questionCount} />
          <DataLine label='来源资料' value={`${paper.sourceAsset.title}（${paper.sourceAsset.code}）`} />
        </>
      ) : null}
      {firstQuestion ? (
        <View className='v2-question'>
          <Text className='v2-question-no'>{firstQuestion.questionNo}</Text>
          <Text>{firstQuestion.content}</Text>
        </View>
      ) : null}
    </Card>
  )
}

function GenerationCard() {
  const [result, setResult] = useState<V2GenerationResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')

  const handleCreate = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setResult(await createV2BusinessFlowGeneration())
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`${err.code}: ${err.message}`)
      } else if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('生成请求失败')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  return (
    <Card title='生成结果引用' ok={Boolean(result)}>
      <Text className='v2-help'>点击后通过后端创建 MVP 生成任务；前端不保存 Dify key。</Text>
      <Button className='v2-action' disabled={loading} onClick={handleCreate}>
        {loading ? '生成中...' : '生成引用样例'}
      </Button>
      {error ? <Text className='v2-error-text'>{error}</Text> : null}
      {result ? (
        <>
          <DataLine label='Run ID' value={result.runId} />
          <DataLine label='模型路由' value={result.modelRoute} />
          <DataLine label='引用数量' value={result.citations.length} />
          <DataLine label='首张卡片' value={result.cards[0]?.title} />
        </>
      ) : null}
    </Card>
  )
}

function CertificateList({ snapshot }: { snapshot: V2BusinessFlowSnapshot }) {
  const items = snapshot.certificateList.data?.items ?? []
  return (
    <View className='v2-cert-strip'>
      {items.map(item => (
        <View key={item.code} className={`v2-cert-chip ${item.code === snapshot.config.certificateCode ? 'active' : ''}`}>
          <Text>{item.name}</Text>
          <Text>{item.code}</Text>
        </View>
      ))}
    </View>
  )
}

export default function V2BusinessFlow() {
  const [snapshot, setSnapshot] = useState<V2BusinessFlowSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadSnapshot = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setSnapshot(await fetchV2BusinessFlowSnapshot())
    } catch (err) {
      setError(err instanceof Error ? err.message : '闭环数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadSnapshot()
  }, [loadSnapshot])

  return (
    <View className='v2-flow-page'>
      <View className='v2-flow-header'>
        <View>
          <Text className='v2-flow-kicker'>V2 MVP</Text>
          <Text className='v2-flow-title'>真实数据业务闭环</Text>
          <Text className='v2-flow-desc'>证书、考试、报考条件、知识检索、题库、权限和生成引用统一从后端读取。</Text>
        </View>
        <Button className='v2-refresh' disabled={loading} onClick={loadSnapshot}>
          {loading ? '加载中' : '刷新'}
        </Button>
      </View>

      <ScrollView className='v2-flow-scroll' scrollY>
        {error ? <Text className='v2-error-text'>{error}</Text> : null}
        {snapshot ? (
          <>
            <CertificateList snapshot={snapshot} />
            <View className='v2-grid'>
              <CertificateCard result={snapshot.certificateDetail} />
              <ExamCard result={snapshot.examEvents} />
              <EligibilityCard title='报考条件判断' result={snapshot.eligibility} />
              <KnowledgeCard result={snapshot.knowledgeSearch} />
              <QuestionCard result={snapshot.questionBank} />
              <PermissionCard result={snapshot.restrictedKnowledgeSearch} />
              <EligibilityCard title='一建数据缺口' result={snapshot.gapEligibility} />
              <GenerationCard />
            </View>
          </>
        ) : (
          <View className='v2-empty'>
            <Text>{loading ? '正在加载 V2 后端数据...' : '暂无数据'}</Text>
          </View>
        )}
      </ScrollView>
    </View>
  )
}
