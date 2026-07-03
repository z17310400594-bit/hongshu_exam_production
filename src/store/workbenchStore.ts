import { create } from 'zustand'

export type ToolKey = 'xhs-content' | 'topic-finder' | 'settings'

interface WorkbenchState {
  activeTool: ToolKey
  setActiveTool: (tool: ToolKey) => void
}

export const useWorkbenchStore = create<WorkbenchState>(set => ({
  activeTool: 'xhs-content',
  setActiveTool: (tool: ToolKey) => set({ activeTool: tool }),
}))
