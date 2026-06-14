import type { StyleToken } from '@/types/exam-article'

/**
 * 卡片风格 CSS Token 定义
 * 风格与内容分离，切换风格不消耗 AI Token
 */
export const STYLE_TOKENS: StyleToken[] = [
  {
    key: 'medical-blue',
    name: '医考蓝',
    cssVars: {
      '--card-bg': '#FFFFFF',
      '--card-bg-gradient': 'linear-gradient(160deg, #EBF5FB 0%, #FFFFFF 60%)',
      '--title-color': '#1A6FB5',
      '--title-size': '17px',
      '--body-color': '#334155',
      '--body-size': '12px',
      '--accent-color': '#E85D3A',
      '--tag-bg': '#EBF5FB',
      '--tag-color': '#1A6FB5',
      '--divider-color': '#E2E8F0',
      '--card-radius': '10px',
      '--shadow': '0 2px 12px rgba(0,0,0,0.06)',
    },
  },
  {
    key: 'study-pink',
    name: '学霸粉',
    cssVars: {
      '--card-bg': '#FFFBFC',
      '--card-bg-gradient': 'linear-gradient(160deg, #FFF0F5 0%, #FFFBFC 60%)',
      '--title-color': '#C82D6B',
      '--title-size': '18px',
      '--body-color': '#4A3548',
      '--body-size': '12px',
      '--accent-color': '#FF6B9D',
      '--tag-bg': '#FFF0F5',
      '--tag-color': '#C82D6B',
      '--divider-color': '#F5E0EA',
      '--card-radius': '14px',
      '--shadow': '0 3px 16px rgba(200,45,107,0.08)',
    },
  },
  {
    key: 'minimal-gray',
    name: '极简灰',
    cssVars: {
      '--card-bg': '#FAFAFA',
      '--card-bg-gradient': 'linear-gradient(180deg, #FAFAFA 0%, #F5F5F5 100%)',
      '--title-color': '#1A1A1A',
      '--title-size': '18px',
      '--body-color': '#525252',
      '--body-size': '12px',
      '--accent-color': '#3B82F6',
      '--tag-bg': '#F0F0F0',
      '--tag-color': '#1A1A1A',
      '--divider-color': '#E5E5E5',
      '--card-radius': '4px',
      '--shadow': '0 1px 3px rgba(0,0,0,0.1)',
    },
  },
]

/** 默认风格 */
export const DEFAULT_STYLE_KEY = 'medical-blue'

/** 根据 key 查找风格 */
export function getStyleByKey(key: string): StyleToken | undefined {
  return STYLE_TOKENS.find(s => s.key === key)
}
