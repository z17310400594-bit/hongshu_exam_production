import { View, Text } from '@tarojs/components'
import { useWorkbenchStore, type ToolKey } from '@/store/workbenchStore'
import { isV2BusinessFlowEnabled } from '@/services/v2BusinessFlowApi'

interface NavItem {
  key: ToolKey
  label: string
  icon: string
}

const MAIN_ITEMS: NavItem[] = [
  { key: 'content-producer', label: '内容生产', icon: '📝' },
  { key: 'topic-finder', label: '选题分析', icon: '📊' },
  ...(isV2BusinessFlowEnabled() ? [{ key: 'v2-flow' as ToolKey, label: 'V2闭环', icon: '🧭' }] : []),
  { key: 'more-tools', label: '更多功能', icon: '⚙️' },
]

const BOTTOM_ITEMS: NavItem[] = [
  { key: 'settings', label: '设置', icon: '🔧' },
]

export default function LeftNav() {
  const activeTool = useWorkbenchStore(s => s.activeTool)
  const setActiveTool = useWorkbenchStore(s => s.setActiveTool)

  return (
    <View className='nav-sidebar'>
      {/* Logo */}
      <View className='nav-logo'>
        <Text>📕</Text>
      </View>

      {/* 主导航项 */}
      {MAIN_ITEMS.map(item => (
        <View
          key={item.key}
          className={`nav-item ${activeTool === item.key ? 'active' : ''}`}
          onClick={() => setActiveTool(item.key)}
        >
          <Text className='nav-icon'>{item.icon}</Text>
          <Text className='nav-label'>{item.label}</Text>
        </View>
      ))}

      {/* 弹性分隔 */}
      <View className='nav-spacer' />

      {/* 底部导航项 */}
      <View className='nav-bottom'>
        {BOTTOM_ITEMS.map(item => (
          <View
            key={item.key}
            className={`nav-item ${activeTool === item.key ? 'active' : ''}`}
            onClick={() => setActiveTool(item.key)}
          >
            <Text className='nav-icon'>{item.icon}</Text>
            <Text className='nav-label'>{item.label}</Text>
          </View>
        ))}
      </View>
    </View>
  )
}
