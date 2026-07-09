import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { StateCreator } from 'zustand'
import { createAuthSlice, type AuthSlice } from './authStore'
import { createLearnerSlice, type LearnerSlice } from './learnerStore'
import { createKnowledgeSlice, type KnowledgeSliceState } from './knowledgeStore'
import { createAgentSlice, createMetricsSlice, type AgentSlice, type MetricsSlice } from './agentStore'
import { createResourceSlice, type ResourceSlice } from './resourceStore'

interface UISlice {
  isDarkMode: boolean
  isSidebarCollapsed: boolean
  toggleDarkMode: () => void
  toggleSidebar: () => void
}

export type AppState = UISlice & AuthSlice & LearnerSlice & KnowledgeSliceState & AgentSlice & MetricsSlice & ResourceSlice

const createUISlice: StateCreator<AppState, [], [], UISlice> = (set) => ({
  isDarkMode: false,
  isSidebarCollapsed: false,
  toggleDarkMode: () => set((state) => {
    const newValue = !state.isDarkMode
    if (typeof document !== 'undefined') {
      if (newValue) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    }
    return { isDarkMode: newValue }
  }),
  toggleSidebar: () => set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),
})

export const useStore = create<AppState>()(
  persist(
    (...a) => ({
      ...createUISlice(...a),
      ...createAuthSlice(...a),
      ...createLearnerSlice(...a),
      ...createKnowledgeSlice(...a),
      ...createAgentSlice(...a),
      ...createMetricsSlice(...a),
      ...createResourceSlice(...a),
    }),
    {
      name: 'multi-agent-system-store',
      partialize: (state) => ({
        isDarkMode: state.isDarkMode,
        isSidebarCollapsed: state.isSidebarCollapsed,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          if (state.isDarkMode && typeof document !== 'undefined') {
            document.documentElement.classList.add('dark')
          }
          setTimeout(() => state.initializeAuth(), 0)
        }
      },
    },
  ),
)
