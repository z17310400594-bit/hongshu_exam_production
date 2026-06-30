import { create } from 'zustand'

export type ToolKey = 'content-producer' | 'topic-finder' | 'v2-flow' | 'more-tools' | 'settings'

interface WorkbenchState {
  activeTool: ToolKey
  setActiveTool: (tool: ToolKey) => void
}

export const useWorkbenchStore = create<WorkbenchState>(set => ({
  activeTool: 'content-producer',
  setActiveTool: (tool: ToolKey) => set({ activeTool: tool }),
}))
