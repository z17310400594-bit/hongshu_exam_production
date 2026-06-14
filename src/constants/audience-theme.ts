/** V1.1 目标人群标签 */
export const TARGET_AUDIENCES = [
  { key: '在职备考', label: '在职备考' },
  { key: '宝妈备考', label: '宝妈备考' },
  { key: '零基础', label: '零基础' },
  { key: '非科班', label: '非科班' },
] as const

export type AudienceKey = (typeof TARGET_AUDIENCES)[number]['key']

/** V1.1 主题预设 */
export const THEME_PRESETS = [
  '考前 30 天冲刺攻略',
] as const

export type ThemePreset = (typeof THEME_PRESETS)[number]
