import { create } from 'zustand'

export type ToolKey = 'content-producer' | 'topic-finder' | 'more-tools' | 'settings'

interface WorkbenchState {
  activeTool: ToolKey
  setActiveTool: (tool: ToolKey) => void
}

export const useWorkbenchStore = create<WorkbenchState>(set => ({
  activeTool: 'content-producer',
  setActiveTool: (tool: ToolKey) => set({ activeTool: tool }),
}))
