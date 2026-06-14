import { useCallback } from 'react'
import html2canvas from 'html2canvas'

interface ExportOptions {
  /** 卡片 3:4 比例宽度（px） */
  width?: number
  /** 文件名前缀 */
  filenamePrefix?: string
  /** 导出进度回调 */
  onProgress?: (current: number, total: number) => void
}

const DEFAULT_WIDTH = 630 // 3:4 → 630×840（小红书推荐尺寸）
const DEFAULT_HEIGHT = 840

/**
 * 卡片导出 Hook
 * 基于 html2canvas 实现 PNG 单张/全部/分层导出
 */
export function useCardExport() {
  /**
   * 截取单个 DOM 元素为 PNG 并触发下载
   */
  const captureAndDownload = useCallback(
    async (element: HTMLElement, filename: string, backgroundColor: string | null = '#FFFFFF') => {
      const canvas = await html2canvas(element, {
        width: DEFAULT_WIDTH,
        height: DEFAULT_HEIGHT,
        scale: 2, // 2x 清晰度
        useCORS: true,
        allowTaint: true,
        backgroundColor: backgroundColor,
      })

      const blob = await new Promise<Blob | null>(resolve => {
        canvas.toBlob(resolve, 'image/png')
      })

      if (!blob) return

      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${filename}.png`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    },
    [],
  )

  /**
   * 导出全部卡片 PNG（每张独立下载）
   */
  const exportAll = useCallback(
    async (options?: ExportOptions) => {
      const elements = document.querySelectorAll<HTMLElement>('[data-card-index]')
      if (elements.length === 0) return

      const prefix = options?.filenamePrefix ?? 'card'
      const total = elements.length

      for (let i = 0; i < elements.length; i++) {
        options?.onProgress?.(i + 1, total)
        // 短暂高亮当前卡片
        elements[i].style.outline = '3px solid #4F46E5'
        await new Promise(r => setTimeout(r, 150))
        await captureAndDownload(elements[i], `${prefix}_${i + 1}`)
        elements[i].style.outline = ''
      }
    },
    [captureAndDownload],
  )

  /**
   * 导出单张卡片 PNG
   */
  const exportSingle = useCallback(
    async (cardIndex: number, filename?: string) => {
      const elements = document.querySelectorAll<HTMLElement>('[data-card-index]')
      const el = elements[cardIndex]
      if (!el) return

      el.style.outline = '3px solid #4F46E5'
      await new Promise(r => setTimeout(r, 100))
      await captureAndDownload(el, filename ?? `card_${cardIndex + 1}`)
      el.style.outline = ''
    },
    [captureAndDownload],
  )

  /**
   * 分层导出：每张卡片生成 3 张透明 PNG（底层/中层/上层），供稿定设计使用
   *
   * 实现策略：
   * - 底层（_bg）：隐藏所有文字节点，只保留背景
   * - 中层（_title）：隐藏正文，只保留标题（半透明背景）
   * - 上层（_body）：隐藏标题和背景装饰，只保留正文内容
   */
  const exportLayered = useCallback(
    async (options?: ExportOptions) => {
      const elements = document.querySelectorAll<HTMLElement>('[data-card-index]')
      if (elements.length === 0) return

      const prefix = options?.filenamePrefix ?? 'card'
      const total = elements.length

      for (let i = 0; i < elements.length; i++) {
        options?.onProgress?.(i + 1, total)
        const el = elements[i]
        el.style.outline = '3px solid #4F46E5'
        await new Promise(r => setTimeout(r, 100))

        // 保存原始状态
        const originalVisibility = saveVisibility(el)

        try {
          // 底层：只保留背景，隐藏所有文字
          hideTextNodes(el)
          await captureAndDownload(el, `${prefix}_${i + 1}_bg`, null) // 透明底
          restoreVisibility(el, originalVisibility)

          // 中层：隐藏正文，只保留标题区和装饰
          hideBodyNodes(el)
          await captureAndDownload(el, `${prefix}_${i + 1}_title`, null)
          restoreVisibility(el, originalVisibility)

          // 上层：隐藏标题和背景，只保留正文
          hideTitleAndBg(el)
          await captureAndDownload(el, `${prefix}_${i + 1}_body`, null)
          restoreVisibility(el, originalVisibility)
        } finally {
          restoreVisibility(el, originalVisibility)
          el.style.outline = ''
        }
      }
    },
    [captureAndDownload],
  )

  return { exportAll, exportSingle, exportLayered }
}

// ===== 辅助函数：分层导出的 DOM 操作 =====

interface SavedVisibility {
  textNodes: { el: HTMLElement; orig: string }[]
  titleNodes: { el: HTMLElement; orig: string }[]
  bodyNodes: { el: HTMLElement; orig: string }[]
  bgNodes: { el: HTMLElement; orig: string }[]
}

function saveVisibility(root: HTMLElement): SavedVisibility {
  const result: SavedVisibility = { textNodes: [], titleNodes: [], bodyNodes: [], bgNodes: [] }

  // 保存所有可操作元素的 visibility
  root.querySelectorAll('.card-title, .card-subtitle, .card-countdown, .plan-list, .tag-list, .items-detail, .notice-list, .cta-block, .card-divider, .day-more, .qr-placeholder, .qr-hint, .cta-main, .cta-sub').forEach(el => {
    const htmlEl = el as HTMLElement
    result.textNodes.push({ el: htmlEl, orig: htmlEl.style.visibility })
  })

  return result
}

function restoreVisibility(_root: HTMLElement, saved: SavedVisibility) {
  ;[...saved.textNodes, ...saved.titleNodes, ...saved.bodyNodes, ...saved.bgNodes].forEach(({ el, orig }) => {
    el.style.visibility = orig
  })
}

function hideTextNodes(root: HTMLElement) {
  root.querySelectorAll('.card-title, .card-subtitle, .card-countdown, .plan-list, .tag-list, .items-detail, .notice-list, .cta-block, .day-more, .qr-placeholder, .qr-hint, .cta-main, .cta-sub').forEach(el => {
    (el as HTMLElement).style.visibility = 'hidden'
  })
}

function hideBodyNodes(root: HTMLElement) {
  // 保留标题，隐藏正文
  root.querySelectorAll('.card-subtitle, .card-countdown, .plan-list, .tag-list, .items-detail, .notice-list, .day-more, .qr-placeholder, .qr-hint, .cta-main, .cta-sub').forEach(el => {
    (el as HTMLElement).style.visibility = 'hidden'
  })
}

function hideTitleAndBg(root: HTMLElement) {
  // 隐藏标题、背景装饰、分割线，只保留正文
  root.querySelectorAll('.card-title, .card-subtitle, .card-divider, .card-countdown, .cta-main, .cta-sub').forEach(el => {
    (el as HTMLElement).style.visibility = 'hidden'
  })
}
