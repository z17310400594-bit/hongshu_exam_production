/**
 * 安全复制文本到剪贴板
 * 优先使用 navigator.clipboard API（需要 HTTPS/localhost），
 * 失败时自动降级为 document.execCommand('copy')
 */
export async function copyToClipboard(text: string): Promise<void> {
  // 路径 1：现代 Clipboard API
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch {
      // 静默降级到 execCommand
    }
  }

  // 路径 2：降级方案 — textarea + execCommand
  const textarea = document.createElement('textarea')
  textarea.value = text
  // 防止滚动
  textarea.style.position = 'fixed'
  textarea.style.top = '-9999px'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()

  try {
    document.execCommand('copy')
  } catch {
    // 最终兜底：提示用户手动复制
    throw new Error('复制失败，请手动选中文本复制')
  } finally {
    document.body.removeChild(textarea)
  }
}
