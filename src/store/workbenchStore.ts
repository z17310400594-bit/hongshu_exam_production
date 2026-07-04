import { create } from 'zustand'

export type ToolKey = 'condensed-handout' | 'xhs-content' | 'topic-finder' | 'settings'

interface WorkbenchState {
  activeTool: ToolKey
  setActiveTool: (tool: ToolKey) => void
}

export const useWorkbenchStore = create<WorkbenchState>(set => ({
  activeTool: 'condensed-handout',
  setActiveTool: (tool: ToolKey) => set({ activeTool: tool }),
}))
