import { View, Text } from '@tarojs/components'
import { useWorkbenchStore, type ToolKey } from '@/store/workbenchStore'

interface NavItem {
  key: ToolKey
  label: string
  icon: string
}

const MAIN_ITEMS: NavItem[] = [
  { key: 'condensed-handout', label: '西药讲义', icon: '📘' },
  { key: 'xhs-content', label: '陪跑生成', icon: '✍️' },
  { key: 'topic-finder', label: '选题分析', icon: '📊' },
]

const BOTTOM_ITEMS: NavItem[] = [
  { key: 'settings', label: '设置', icon: '🔧' },
]

export default function LeftNav() {
  const activeTool = useWorkbenchStore(s => s.activeTool)
  const setActiveTool = useWorkbenchStore(s => s.setActiveTool)

  return (
    <View className='nav-sidebar'>
      <View className='nav-logo'>
        <Text>📩</Text>
      </View>

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

      <View className='nav-spacer' />

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
