import { View, Text } from '@tarojs/components'
import { useLoad } from '@tarojs/taro'
import { Suspense, lazy } from 'react'
import { useWorkbenchStore } from '@/store/workbenchStore'
import LeftNav from './components/LeftNav'
import './index.scss'

const TopicFinder = lazy(() => import('./components/TopicFinder'))
const XhsContentGenerator = lazy(() => import('./components/XhsContentGenerator'))

function LoadingFallback() {
  return (
    <View className='loading-fallback'>
      <View className='loading-spinner'>⏳</View>
      <Text className='loading-text'>加载中...</Text>
    </View>
  )
}

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

  useLoad(() => {
    // Reserved for login/session checks in production.
  })

  return (
    <View className='workbench'>
      <LeftNav />

      <View className='main-content'>
        <View className={`page-view ${activeTool === 'xhs-content' ? 'active' : ''}`}>
          <Suspense fallback={<LoadingFallback />}>
            <XhsContentGenerator />
          </Suspense>
        </View>

        <View className={`page-view ${activeTool === 'topic-finder' ? 'active' : ''}`}>
          <Suspense fallback={<LoadingFallback />}>
            <TopicFinder />
          </Suspense>
        </View>

        <View className={`page-view ${activeTool === 'settings' ? 'active' : ''}`}>
          <PlaceholderPage
            icon='🔧'
            title='设置'
            desc='账号管理、API 密钥配置、偏好设置等功能即将上线'
          />
        </View>
      </View>
    </View>
  )
}
