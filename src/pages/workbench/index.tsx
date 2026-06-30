import { View, Text } from '@tarojs/components'
import { useLoad } from '@tarojs/taro'
import { Suspense, lazy } from 'react'
import { useWorkbenchStore } from '@/store/workbenchStore'
import { isV2BusinessFlowEnabled } from '@/services/v2BusinessFlowApi'
import LeftNav from './components/LeftNav'
import './index.scss'

const TopicFinder = lazy(() => import('./components/TopicFinder'))
const ExamArticle = lazy(() => import('./components/ExamArticle'))
const V2BusinessFlow = lazy(() => import('./components/V2BusinessFlow'))

function LoadingFallback() {
  return (
    <View className='loading-fallback'>
      <View className='loading-spinner'>⏳</View>
      <Text className='loading-text'>加载中...</Text>
    </View>
  )
}

/** 占位页面 */
function PlaceholderPage({ icon, title, desc }: { icon: string; title: string; desc: string }) {
  return (
    <View className='placeholder-page'>
      <Text className='placeholder-icon'>{icon}</Text>
      <Text className='placeholder-title'>{title}</Text>
      <Text className='placeholder-desc'>{desc}</Text>
    </View>
  )
}

export default function Workbench() {
  const activeTool = useWorkbenchStore(s => s.activeTool)
  const showV2BusinessFlow = isV2BusinessFlowEnabled()

  useLoad(() => {
    // 线上环境可在此做登录态校验等
  })

  return (
    <View className='workbench'>
      <LeftNav />

      {/* 主内容区 — 用 page-view 模式，与原型一致 */}
      <View className='main-content'>
        <View className={`page-view ${activeTool === 'content-producer' ? 'active' : ''}`}>
          <Suspense fallback={<LoadingFallback />}>
            <ExamArticle />
          </Suspense>
        </View>

        <View className={`page-view ${activeTool === 'topic-finder' ? 'active' : ''}`}>
          <Suspense fallback={<LoadingFallback />}>
            <TopicFinder />
          </Suspense>
        </View>

        {showV2BusinessFlow ? (
          <View className={`page-view ${activeTool === 'v2-flow' ? 'active' : ''}`}>
            <Suspense fallback={<LoadingFallback />}>
              <V2BusinessFlow />
            </Suspense>
          </View>
        ) : null}

        <View className={`page-view ${activeTool === 'more-tools' ? 'active' : ''}`}>
          <PlaceholderPage
            icon='🛠️'
            title='更多功能'
            desc='考试模板预设库、风格在线预览、素材库升级 等更多功能即将上线'
          />
        </View>

        <View className={`page-view ${activeTool === 'settings' ? 'active' : ''}`}>
          <PlaceholderPage
            icon='🔧'
            title='设置'
            desc='账号管理、API 密钥配置、偏好设置 等功能即将上线'
          />
        </View>
      </View>
    </View>
  )
}
