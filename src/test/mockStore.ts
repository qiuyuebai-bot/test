type State = Record<string, unknown>

const defaults: State = {
  isDarkMode: false,
  isSidebarCollapsed: false,
  toggleDarkMode: () => {},
  toggleSidebar: () => {},
  user: { id: 1, username: 'admin', role: 'admin' },
  isLoggedIn: true,
  isLoading: false,
  login: () => Promise.resolve(),
  logout: () => Promise.resolve(),
  fetchCurrentUser: () => Promise.resolve(),
  initializeAuth: () => {},
  learners: [],
  currentLearner: null,
  learnersLoading: false,
  learnerLoading: false,
  learnersTotal: 0,
  pagination: { page: 1, pageSize: 20, total: 0, totalPages: 0 },
  fetchLearners: () => Promise.resolve(),
  fetchLearnerById: () => Promise.resolve(),
  setCurrentLearner: () => {},
  createLearner: () => Promise.resolve({ id: 1 }),
  addLearner: () => Promise.resolve({ id: 1 }),
  updateLearner: () => Promise.resolve({ id: 1 }),
  deleteLearner: () => Promise.resolve(),
  knowledgeDocs: [],
  knowledgeSlices: [],
  knowledgeLoading: false,
  knowledgeError: null,
  totalKnowledgeDocs: 0,
  currentPage: 1,
  pageSize: 50,
  fetchKnowledgeDocs: () => Promise.resolve(),
  fetchKnowledgeSlices: () => Promise.resolve(),
  agentStatuses: [],
  tasks: [],
  tasksTotal: 0,
  currentTask: null,
  agentsLoading: false,
  fetchAgentStatuses: () => Promise.resolve(),
  fetchTasks: () => Promise.resolve(),
  startAgentTask: () => Promise.resolve({ taskId: 1 }),
  runFullPipeline: () => Promise.resolve({ taskId: 1 }),
  pollTaskStatus: () => () => {},
  setCurrentTask: () => {},
  systemMetrics: null,
  metricsLoading: false,
  fetchSystemMetrics: () => Promise.resolve(),
  resources: [],
  resourcesTotal: 0,
  resourcesLoading: false,
  resourceLoading: false,
  fetchResources: () => Promise.resolve(),
  generateResources: () => Promise.resolve({ taskId: '1' }),
  generateResource: () => Promise.resolve({}),
}

export const mockStoreState: State = { ...defaults }

export function resetMockStore(): void {
  Object.assign(mockStoreState, defaults)
}

export function setMockStore(overrides: Record<string, unknown>): void {
  Object.assign(mockStoreState, overrides)
}

function useStoreMock(selector?: (s: State) => unknown): unknown {
  return selector ? selector(mockStoreState) : mockStoreState
}
useStoreMock.getState = () => mockStoreState
useStoreMock.setState = (partial: Record<string, unknown>) => {
  Object.assign(mockStoreState, partial)
}

export { useStoreMock }
