import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Eye,
  EyeOff,
  KeyRound,
  Link2,
  Loader2,
  RefreshCw,
  ServerCog,
  ShieldCheck,
  Trash2,
  Wifi,
  XCircle,
} from 'lucide-react'
import Card from '@/components/Card'
import Button from '@/components/Button'
import Input from '@/components/Input'
import Modal from '@/components/Modal'
import { aiConfigApi, AI_PROVIDER_OPTIONS } from '@/api'
import { DEFAULT_AI_GENERATION_PARAM_META } from '@/api/aiConfig'
import type {
  AiConfig,
  AiConfigTestResult,
  AiConfigUpdateRequest,
  AiGenerationParamMeta,
  AiGenerationParamsState,
  AiGenerationParamValue,
  AiProviderGroup,
  AiProviderOption,
} from '@/api/aiConfig'
import { ApiError } from '@/lib/request'
import { toast } from '@/components/toastStore'

interface AiConfigDraft {
  provider: string
  protocol: string
  baseUrl: string
  selectedModel: string
  apiKey: string
  proxyUrl: string
  proxyPassword: string
  projectId: string
  location: string
  region: string
  generationParams: Record<string, AiGenerationParamValue>
}

const GROUP_LABELS: Record<AiProviderGroup, string> = {
  custom: '自定义接入',
  official: '官方服务',
  gateway: '聚合平台',
  local: '本地服务',
}

const EMPTY_CONFIG: AiConfig = {
  provider: 'custom',
  protocol: 'openai_chat',
  baseUrl: '',
  selectedModel: null,
  availableModels: [],
  apiKeyConfigured: false,
  apiKeyHint: null,
  proxyUrl: '',
  proxyPasswordConfigured: false,
  lastTestStatus: 'never',
  lastTestMessage: null,
  lastTestedAt: null,
  generationParams: {},
  generationParamsMeta: DEFAULT_AI_GENERATION_PARAM_META,
  generationParamsSupported: true,
}

function toDraft(config: AiConfig): AiConfigDraft {
  const extraConfig = config.extraConfig || {}
  const meta = config.generationParamsMeta?.length
    ? config.generationParamsMeta
    : DEFAULT_AI_GENERATION_PARAM_META
  return {
    provider: config.provider,
    protocol: config.protocol,
    baseUrl: config.baseUrl,
    selectedModel: config.selectedModel || '',
    apiKey: '',
    proxyUrl: config.proxyUrl || '',
    proxyPassword: '',
    projectId: typeof extraConfig.projectId === 'string' ? extraConfig.projectId : '',
    location: typeof extraConfig.location === 'string' ? extraConfig.location : '',
    region: typeof extraConfig.region === 'string' ? extraConfig.region : '',
    generationParams: normalizeGenerationParams(config, meta),
  }
}

function modelConfigKey(provider: string, model: string): string {
  return `${provider}:${model || '__default__'}`
}

function getDefaultParamValue(meta: AiGenerationParamMeta): AiGenerationParamValue {
  if (meta.defaultValue !== undefined) return meta.defaultValue
  if (meta.default !== undefined) return meta.default
  if (meta.value !== undefined) return meta.value
  if (meta.type === 'boolean') return false
  if (meta.type === 'number') return 0
  return ''
}

function defaultGenerationParams(
  meta: AiGenerationParamMeta[],
): Record<string, AiGenerationParamValue> {
  return meta.reduce<Record<string, AiGenerationParamValue>>((result, item) => {
    if (item.supported !== false) result[item.key] = getDefaultParamValue(item)
    return result
  }, {})
}

function normalizeGenerationParams(
  config: AiConfig,
  meta: AiGenerationParamMeta[],
): Record<string, AiGenerationParamValue> {
  // A generationParams field from the new API is deliberately sparse: it is
  // the set of values the user chose to send for this provider/model. This is
  // what makes removing an entry durable. Only the legacy API (field absent)
  // falls back to the four ordinary defaults.
  if (config.generationParamsConfigured === false) return defaultGenerationParams(meta)
  if (config.generationParamsConfigured === true) return { ...(config.generationParams || {}) }
  if (config.generationParams !== undefined) return { ...config.generationParams }
  return defaultGenerationParams(meta)
}

function resolveGenerationParams(
  config: AiConfig,
  snapshots: Record<string, Record<string, AiGenerationParamValue>>,
): Record<string, AiGenerationParamValue> {
  const meta = config.generationParamsMeta?.length
    ? config.generationParamsMeta
    : DEFAULT_AI_GENERATION_PARAM_META
  const key = modelConfigKey(config.provider, config.selectedModel || '')
  // An older backend has no generation fields and cannot persist them. Use the
  // non-sensitive local snapshot in that case; a server-provided value always
  // wins once the upgraded endpoint advertises support.
  if (config.generationParamsSupported === false && snapshots[key]) {
    return { ...snapshots[key] }
  }
  return normalizeGenerationParams(config, meta)
}

function initialParamsForUnseenModel(
  generationParamsSupported: boolean | undefined,
  meta: AiGenerationParamMeta[],
): Record<string, AiGenerationParamValue> {
  // Newer servers use a sparse profile: an unseen model starts with no
  // explicit wire parameters and therefore inherits the provider default.
  // Older servers do not expose the support marker, so retain the historical
  // four-value fallback until the endpoint is upgraded.
  return generationParamsSupported === true ? {} : defaultGenerationParams(meta)
}

function normalizeGenerationParamMeta(item: AiGenerationParamMeta): AiGenerationParamMeta {
  const inferredType: AiGenerationParamMeta['type'] =
    item.type ||
    (typeof item.value === 'boolean' ||
    typeof item.defaultValue === 'boolean' ||
    typeof item.default === 'boolean'
      ? 'boolean'
      : typeof item.value === 'number' ||
          typeof item.defaultValue === 'number' ||
          typeof item.default === 'number'
        ? 'number'
        : 'number')
  return {
    ...item,
    type: inferredType,
    label: item.label || item.key,
    step: inferredType === 'number' ? item.step || 0.01 : item.step,
  }
}

function mergeGenerationParamMeta(
  meta: AiGenerationParamMeta[],
  values: Record<string, AiGenerationParamValue>,
): AiGenerationParamMeta[] {
  const normalized = meta.map(normalizeGenerationParamMeta)
  const known = new Set(normalized.map((item) => item.key))
  Object.entries(values).forEach(([key, value]) => {
    if (known.has(key)) return
    normalized.push(
      normalizeGenerationParamMeta({
        key,
        label: key,
        type:
          typeof value === 'boolean' ? 'boolean' : typeof value === 'number' ? 'number' : 'string',
        value,
        defaultValue: value,
      }),
    )
  })
  return normalized
}

function generationParamStorageKey(): string {
  if (typeof window === 'undefined') return 'ai-generation-params:anonymous'
  try {
    const raw = window.localStorage.getItem('user_info')
    if (raw) {
      const parsed = JSON.parse(raw) as { user_id?: unknown; userId?: unknown }
      const userId = parsed.userId ?? parsed.user_id
      if (typeof userId === 'number' || typeof userId === 'string') {
        return `ai-generation-params:${String(userId)}`
      }
    }
  } catch {
    // A malformed local user record must never prevent the AI page from opening.
  }
  return 'ai-generation-params:anonymous'
}

function readGenerationParamSnapshots(): Record<string, Record<string, AiGenerationParamValue>> {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(generationParamStorageKey())
    if (!raw) return {}
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    return parsed as Record<string, Record<string, AiGenerationParamValue>>
  } catch {
    return {}
  }
}

function writeGenerationParamSnapshots(
  snapshots: Record<string, Record<string, AiGenerationParamValue>>,
): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(generationParamStorageKey(), JSON.stringify(snapshots))
  } catch {
    // Storage can be disabled; the server remains the source of truth after a test.
  }
}

function coerceGenerationParamValue(
  value: string,
  meta: AiGenerationParamMeta,
): AiGenerationParamValue | undefined {
  if (meta.type === 'boolean') return value === 'true'
  if (meta.type === 'string') return value
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return undefined
  return parsed
}

function formatGenerationParamValue(value: AiGenerationParamValue): string {
  if (value === null) return '默认'
  if (typeof value === 'boolean') return value ? '开启' : '关闭'
  return String(value)
}

function providerFromCatalog(
  provider: string,
  options: AiProviderOption[],
): AiProviderOption | undefined {
  return options.find((option) => option.id === provider)
}

function isProviderImplemented(provider?: AiProviderOption): boolean {
  if (!provider) return false
  const needsDedicatedAdapter =
    provider.protocol === 'anthropic_messages' || provider.protocol === 'gemini'
  return provider.implemented === true || (!needsDedicatedAdapter && provider.implemented !== false)
}

function resolveProviderOptions(remoteOptions?: AiProviderOption[]): AiProviderOption[] {
  if (remoteOptions?.length) {
    return remoteOptions.filter(
      (option): option is AiProviderOption =>
        Boolean(option) &&
        typeof option.id === 'string' &&
        typeof option.label === 'string' &&
        typeof option.protocol === 'string',
    )
  }
  return AI_PROVIDER_OPTIONS
}

function normalizeUrl(value: string): string {
  return value.trim().replace(/\/+$/, '')
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    // The backend deliberately returns a safe, human-readable message. Never
    // render arbitrary response payloads, which could contain request secrets.
    return error.message || fallback
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}

function statusText(status: AiConfigTestResult['success'] | string | undefined): string {
  if (status === true || status === 'success') return '连接成功'
  if (status === false || status === 'failed') return '连接失败'
  if (status === 'needs_retest') return '需重新测试'
  return '尚未测试'
}

export default function AiConfigPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const isDesktopOnboarding = Boolean(
    window.zhiyuDesktop?.isDesktop && searchParams.get('onboarding') === '1',
  )
  const [config, setConfig] = useState<AiConfig>(EMPTY_CONFIG)
  const [draft, setDraft] = useState<AiConfigDraft>(toDraft(EMPTY_CONFIG))
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [showProxyPassword, setShowProxyPassword] = useState(false)
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false)
  const [isAdvancedWarningOpen, setIsAdvancedWarningOpen] = useState(false)
  const [hasSeenAdvancedWarning, setHasSeenAdvancedWarning] = useState(false)
  const [expandedCustomGenerationParams, setExpandedCustomGenerationParams] = useState<
    Record<string, boolean>
  >({})
  const [requiresRetest, setRequiresRetest] = useState(false)
  const [generationParamDirtyKeys, setGenerationParamDirtyKeys] = useState<Record<string, true>>({})
  const [generationParamRemoteStates, setGenerationParamRemoteStates] = useState<
    Record<string, AiGenerationParamsState>
  >({})
  const [generationParamSnapshots, setGenerationParamSnapshots] = useState<
    Record<string, Record<string, AiGenerationParamValue>>
  >(() => readGenerationParamSnapshots())
  const [loadError, setLoadError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<AiConfigTestResult | null>(null)
  const generationParamSnapshotsRef = useRef(generationParamSnapshots)
  const generationParamDirtyKeysRef = useRef(generationParamDirtyKeys)
  const generationParamRequestIdRef = useRef(0)

  const providerOptions = useMemo(
    () => resolveProviderOptions(config.providerOptions),
    [config.providerOptions],
  )
  const provider = providerFromCatalog(draft.provider, providerOptions)
  const isCustomProvider = draft.provider === 'custom' || provider?.group === 'custom'
  const isLocalProvider = provider?.group === 'local'
  const isAzureOpenAI = draft.provider === 'azure_openai'
  const isVertexAi = draft.provider === 'vertex_ai'
  const isBedrock = draft.provider === 'bedrock'
  const isBaseUrlEditable = isCustomProvider || isLocalProvider || isAzureOpenAI
  const supportsProxy = Boolean(provider?.supportsReverseProxy) && !isCustomProvider
  const requiresApiKey = provider?.requiresApiKey !== false
  const providerImplemented = isProviderImplemented(provider)
  const credentialLabel = isVertexAi
    ? 'Google Cloud 服务账号 JSON'
    : isAzureOpenAI
      ? 'Azure OpenAI API Key'
      : isBedrock
        ? 'Amazon Bedrock API Key'
        : 'API Key'
  const credentialPlaceholder = isVertexAi ? '粘贴服务账号 JSON（保存后不会回显）' : '输入 API Key'
  const modelLabel = isAzureOpenAI ? 'Azure 部署名称' : isVertexAi ? 'Vertex 模型 ID' : '可用模型'
  const modelPlaceholder = isAzureOpenAI
    ? '输入 Azure 部署名称'
    : isVertexAi
      ? '例如：google/gemini-2.5-flash'
      : '连接后自动获取，或手动输入模型 ID'
  const derivedBaseUrl = isVertexAi
    ? draft.projectId.trim() && draft.location.trim()
      ? `https://${draft.location.trim() === 'global' ? 'aiplatform.googleapis.com' : `${draft.location.trim()}-aiplatform.googleapis.com`}/v1/projects/${draft.projectId.trim()}/locations/${draft.location.trim()}/endpoints/openapi`
      : '填写项目 ID 和区域后自动生成'
    : isBedrock
      ? draft.region.trim()
        ? `https://bedrock-mantle.${draft.region.trim()}.api.aws/v1`
        : '填写 AWS 区域后自动生成'
      : ''
  const canReuseApiKey =
    config.source === 'database' && config.apiKeyConfigured && config.provider === draft.provider
  const canReuseProxyPassword =
    config.source === 'database' &&
    config.proxyPasswordConfigured &&
    config.provider === draft.provider
  const canUseProxyCredential =
    supportsProxy &&
    Boolean(normalizeUrl(draft.proxyUrl)) &&
    Boolean(draft.proxyPassword.trim() || canReuseProxyPassword)
  const requiresManualModelEntry =
    provider?.supportsModelsEndpoint === false ||
    (config.lastTestStatus === 'success' && config.availableModels.length === 0)
  const isCurrentPersistedModel =
    config.provider === draft.provider && (config.selectedModel || '') === draft.selectedModel
  const activeModelConfigKey = modelConfigKey(draft.provider, draft.selectedModel)
  const loadedGenerationParamState = generationParamRemoteStates[activeModelConfigKey]
  const generationParamsMeta = useMemo<AiGenerationParamMeta[]>(() => {
    if (isCustomProvider) {
      return DEFAULT_AI_GENERATION_PARAM_META.map((item) => ({ ...item, supported: true }))
    }
    const remoteMeta = isCurrentPersistedModel
      ? config.generationParamsMeta?.filter(
          (item): item is AiGenerationParamMeta => Boolean(item) && typeof item.key === 'string',
        )
      : loadedGenerationParamState?.generationParamsMeta
    const hasReliableMeta = Boolean(remoteMeta?.length)
    const fallbackMeta =
      !isCurrentPersistedModel && !hasReliableMeta
        ? DEFAULT_AI_GENERATION_PARAM_META.map((item) => ({ ...item, supported: false }))
        : DEFAULT_AI_GENERATION_PARAM_META
    const valuesForMeta = isCurrentPersistedModel || hasReliableMeta ? draft.generationParams : {}
    return mergeGenerationParamMeta(hasReliableMeta ? remoteMeta! : fallbackMeta, valuesForMeta)
  }, [
    config.generationParamsMeta,
    draft.generationParams,
    isCurrentPersistedModel,
    loadedGenerationParamState,
    isCustomProvider,
  ])
  const supportedGenerationParamsMeta = generationParamsMeta.filter(
    (item) => item.supported !== false,
  )
  const configuredGenerationParamKeys = Object.keys(draft.generationParams)
  const configuredGenerationParams = supportedGenerationParamsMeta.filter((item) =>
    configuredGenerationParamKeys.includes(item.key),
  )
  const unsupportedGenerationParams = generationParamsMeta.filter(
    (item) => item.supported === false,
  )
  const availableGenerationParams = supportedGenerationParamsMeta.filter(
    (item) => !configuredGenerationParamKeys.includes(item.key),
  )
  const hasLoadedGenerationParamState =
    isCurrentPersistedModel ||
    isCustomProvider ||
    Boolean(loadedGenerationParamState?.generationParamsMeta.length)

  const loadGenerationParamState = useCallback(async (providerId: string, model: string) => {
    const key = modelConfigKey(providerId, model)
    const requestId = ++generationParamRequestIdRef.current
    // Custom endpoints have no safe capability inference. Their generic
    // controls are local to this page, so avoid an unnecessary metadata request.
    if (providerId === 'custom') return
    try {
      const state = await aiConfigApi.getGenerationParams(providerId, model)
      if (requestId !== generationParamRequestIdRef.current) return
      setGenerationParamRemoteStates((current) => ({ ...current, [key]: state }))
      if (generationParamDirtyKeysRef.current[key]) return
      const params = { ...state.generationParams }
      const nextSnapshots = { ...generationParamSnapshotsRef.current, [key]: params }
      generationParamSnapshotsRef.current = nextSnapshots
      setGenerationParamSnapshots(() => nextSnapshots)
      setDraft((current) =>
        modelConfigKey(current.provider, current.selectedModel) === key
          ? { ...current, generationParams: params }
          : current,
      )
    } catch {
      // Older backends may not expose the read-only capability endpoint. The
      // caller keeps the target model's controls hidden until it is tested.
    }
  }, [])

  useEffect(() => {
    generationParamSnapshotsRef.current = generationParamSnapshots
    writeGenerationParamSnapshots(generationParamSnapshots)
  }, [generationParamSnapshots])

  useEffect(() => {
    generationParamDirtyKeysRef.current = generationParamDirtyKeys
  }, [generationParamDirtyKeys])

  const loadConfig = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    generationParamRequestIdRef.current += 1
    try {
      const result = await aiConfigApi.get()
      setConfig(result)
      setGenerationParamRemoteStates({})
      const resultParams =
        result.provider === 'custom' && result.generationParamsConfigured !== true
          ? {}
          : resolveGenerationParams(result, generationParamSnapshotsRef.current)
      setDraft({ ...toDraft(result), generationParams: resultParams })
      const resultKey = modelConfigKey(result.provider, result.selectedModel || '')
      setGenerationParamSnapshots((current) =>
        current[resultKey] && result.generationParamsSupported === false
          ? current
          : { ...current, [resultKey]: resultParams },
      )
      setShowProxyPassword(false)
      setRequiresRetest(false)
      generationParamDirtyKeysRef.current = {}
      setGenerationParamDirtyKeys({})
      setTestResult(null)
    } catch (error: unknown) {
      // A fresh installation may not have an AI config row yet. Treat a 404 as
      // an empty configuration so users can still enter the setup page.
      if (error instanceof ApiError && error.code === 404) {
        setConfig(EMPTY_CONFIG)
        setGenerationParamRemoteStates({})
        setDraft(toDraft(EMPTY_CONFIG))
        const emptyKey = modelConfigKey(EMPTY_CONFIG.provider, '')
        const emptyParams = resolveGenerationParams(
          EMPTY_CONFIG,
          generationParamSnapshotsRef.current,
        )
        setDraft((current) => ({ ...current, generationParams: emptyParams }))
        setGenerationParamSnapshots((current) => ({ ...current, [emptyKey]: emptyParams }))
        setShowProxyPassword(false)
        setRequiresRetest(false)
        generationParamDirtyKeysRef.current = {}
        setGenerationParamDirtyKeys({})
      } else {
        setLoadError(getErrorMessage(error, 'AI 配置加载失败，请稍后重试'))
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadConfig()
  }, [loadConfig])

  const updateDraft = <K extends keyof AiConfigDraft>(key: K, value: AiConfigDraft[K]) => {
    setDraft((current) => ({ ...current, [key]: value }))
    setFormError(null)
  }

  const markGenerationParamsChanged = () => {
    if (!generationParamDirtyKeysRef.current[activeModelConfigKey]) {
      const nextDirtyKeys = {
        ...generationParamDirtyKeysRef.current,
        [activeModelConfigKey]: true as const,
      }
      generationParamDirtyKeysRef.current = nextDirtyKeys
      setGenerationParamDirtyKeys(nextDirtyKeys)
    }
    setRequiresRetest(true)
    setTestResult(null)
    setFormError(null)
  }

  const updateGenerationParam = (key: string, value: AiGenerationParamValue) => {
    const generationParams = { ...draft.generationParams, [key]: value }
    const nextSnapshots = {
      ...generationParamSnapshotsRef.current,
      [activeModelConfigKey]: generationParams,
    }
    generationParamSnapshotsRef.current = nextSnapshots
    setDraft((current) => ({ ...current, generationParams }))
    setGenerationParamSnapshots(() => nextSnapshots)
    markGenerationParamsChanged()
  }

  const addGenerationParam = (key: string) => {
    const meta = supportedGenerationParamsMeta.find((item) => item.key === key)
    if (!meta) return
    updateGenerationParam(key, getDefaultParamValue(meta))
  }

  const removeGenerationParam = (key: string) => {
    const generationParams = { ...draft.generationParams }
    delete generationParams[key]
    const nextSnapshots = {
      ...generationParamSnapshotsRef.current,
      [activeModelConfigKey]: generationParams,
    }
    generationParamSnapshotsRef.current = nextSnapshots
    setDraft((current) => ({ ...current, generationParams }))
    setGenerationParamSnapshots(() => nextSnapshots)
    markGenerationParamsChanged()
  }

  const restoreDefaultGenerationParams = () => {
    if (isCustomProvider) return
    const generationParams = defaultGenerationParams(generationParamsMeta)
    const currentKeys = Object.keys(draft.generationParams)
    const nextKeys = Object.keys(generationParams)
    const unchanged =
      currentKeys.length === nextKeys.length &&
      nextKeys.every((key) => draft.generationParams[key] === generationParams[key])
    if (unchanged) return
    const nextSnapshots = {
      ...generationParamSnapshotsRef.current,
      [activeModelConfigKey]: generationParams,
    }
    generationParamSnapshotsRef.current = nextSnapshots
    setGenerationParamSnapshots(() => nextSnapshots)
    setDraft((current) => ({ ...current, generationParams }))
    markGenerationParamsChanged()
  }

  const handleAdvancedToggle = () => {
    if (!isAdvancedOpen && !hasSeenAdvancedWarning) {
      setIsAdvancedWarningOpen(true)
      return
    }
    setIsAdvancedOpen((current) => !current)
  }

  const confirmAdvancedWarning = () => {
    setHasSeenAdvancedWarning(true)
    setIsAdvancedWarningOpen(false)
    setIsAdvancedOpen(true)
  }

  const handleProviderChange = (nextProvider: string) => {
    const next = providerFromCatalog(nextProvider, providerOptions)
    const nextIsCustomProvider = nextProvider === 'custom' || next?.group === 'custom'
    const nextProviderKey = modelConfigKey(nextProvider, next?.defaultModel || '')
    const snapshots = generationParamSnapshotsRef.current
    const nextParams =
      !nextIsCustomProvider && snapshots[nextProviderKey]
        ? { ...snapshots[nextProviderKey] }
        : initialParamsForUnseenModel(
            config.generationParamsSupported,
            DEFAULT_AI_GENERATION_PARAM_META,
          )
    const nextSnapshots = {
      ...snapshots,
      [nextProviderKey]: nextParams,
    }
    generationParamSnapshotsRef.current = nextSnapshots
    setGenerationParamSnapshots(() => nextSnapshots)
    setDraft((current) => ({
      ...current,
      provider: nextProvider,
      protocol: next?.protocol || 'openai_chat',
      baseUrl: next?.defaultBaseUrl || '',
      selectedModel: next?.defaultModel || '',
      // Keys are never copied between providers. The persisted key remains on
      // the server until the user explicitly clears or replaces it.
      apiKey: '',
      proxyUrl: '',
      proxyPassword: '',
      projectId: '',
      location: nextProvider === 'vertex_ai' ? 'global' : '',
      region: nextProvider === 'bedrock' ? 'us-east-1' : '',
      // A new provider has no explicit parameters until the user adds one.
      // This prevents generic defaults from breaking an incompatible model.
      generationParams: nextParams,
    }))
    setConfig((current) => ({ ...current, availableModels: [] }))
    setShowProxyPassword(false)
    setIsAdvancedOpen(false)
    setRequiresRetest(true)
    setTestResult(null)
    setFormError(null)
    void loadGenerationParamState(nextProvider, next?.defaultModel || '')
  }

  const validate = (): string | null => {
    if (!providerImplemented) {
      return `${provider?.label || '该服务'}尚未完成协议适配，暂不能保存或连接`
    }
    const baseUrl = normalizeUrl(draft.baseUrl)
    if (isVertexAi) {
      if (!draft.projectId.trim()) return '请填写 Google Cloud 项目 ID'
      if (!draft.location.trim()) return '请填写 Google Cloud 区域'
      if (!draft.selectedModel.trim()) return '请填写 Vertex 模型 ID'
    } else if (isBedrock) {
      if (!draft.region.trim()) return '请填写 AWS 区域'
    } else {
      if (!baseUrl) return isCustomProvider ? '请输入 API Base URL' : '请填写服务地址'
      try {
        const parsed = new URL(baseUrl)
        if (!['http:', 'https:'].includes(parsed.protocol))
          return 'API Base URL 只支持 http 或 https'
      } catch {
        return 'API Base URL 格式不正确'
      }
      if (isAzureOpenAI && !draft.selectedModel.trim()) return '请填写 Azure 部署名称'
    }
    if (requiresApiKey && !draft.apiKey.trim() && !canReuseApiKey && !canUseProxyCredential) {
      return isVertexAi
        ? '请粘贴 Google Cloud 服务账号 JSON'
        : `请输入 ${credentialLabel}${supportsProxy ? '；使用反向代理时也可填写代理密码' : ''}`
    }
    if (supportsProxy && draft.proxyUrl.trim()) {
      try {
        const parsed = new URL(normalizeUrl(draft.proxyUrl))
        if (!['http:', 'https:'].includes(parsed.protocol))
          return '代理服务器 URL 只支持 http 或 https'
      } catch {
        return '代理服务器 URL 格式不正确'
      }
    }
    for (const meta of generationParamsMeta) {
      if (meta.supported === false || !(meta.key in draft.generationParams)) continue
      const value = draft.generationParams[meta.key]
      if (meta.type === 'number') {
        const numericValue = typeof value === 'number' ? value : Number(value)
        if (!Number.isFinite(numericValue)) return `${meta.label || meta.key} 必须是有效数字`
        if (meta.min !== undefined && numericValue < meta.min)
          return `${meta.label || meta.key} 不能小于 ${meta.min}`
        if (meta.max !== undefined && numericValue > meta.max)
          return `${meta.label || meta.key} 不能大于 ${meta.max}`
      }
    }
    return null
  }

  const buildPayload = (): AiConfigUpdateRequest => {
    const providerChanged = config.provider !== draft.provider
    let extraConfig: NonNullable<AiConfigUpdateRequest['extraConfig']> = {}
    if (isVertexAi) {
      extraConfig = {
        projectId: draft.projectId.trim(),
        location: draft.location.trim(),
      }
    } else if (isBedrock) {
      extraConfig = { region: draft.region.trim() }
    }
    const payload: AiConfigUpdateRequest = {
      provider: draft.provider,
      protocol: draft.protocol,
      baseUrl: isVertexAi || isBedrock ? '' : normalizeUrl(draft.baseUrl),
      selectedModel: draft.selectedModel || null,
      availableModels: config.availableModels,
      proxyUrl: supportsProxy ? normalizeUrl(draft.proxyUrl) : '',
      extraConfig,
    }
    // Send parameters only after the target model's capabilities are known and
    // the user explicitly changed its profile. An omitted field preserves a
    // profile that may have been saved from another device.
    if (
      config.generationParamsSupported !== false &&
      hasLoadedGenerationParamState &&
      generationParamDirtyKeys[activeModelConfigKey]
    ) {
      const supportedKeys = new Set(
        generationParamsMeta.filter((item) => item.supported !== false).map((item) => item.key),
      )
      payload.generationParams = Object.fromEntries(
        Object.entries(draft.generationParams).filter(([key]) => supportedKeys.has(key)),
      )
    }
    if (draft.apiKey.trim()) payload.apiKey = draft.apiKey.trim()
    else if (providerChanged && canReuseApiKey) payload.clearApiKey = true
    if (supportsProxy && draft.proxyPassword.trim())
      payload.proxyPassword = draft.proxyPassword.trim()
    else if (providerChanged && canReuseProxyPassword) payload.clearProxyPassword = true
    return payload
  }

  const handleTest = async () => {
    const validationError = validate()
    if (validationError) {
      setFormError(validationError)
      return
    }
    setTesting(true)
    setFormError(null)
    setTestResult(null)
    try {
      const payload = buildPayload()
      const result = await aiConfigApi.test(payload)
      setTestResult(result)
      if (result.success) {
        if (result.selectedModel) {
          const saved = await aiConfigApi.get()
          setConfig(saved)
          setDraft(toDraft(saved))
          const savedMeta = saved.generationParamsMeta?.length
            ? saved.generationParamsMeta
            : DEFAULT_AI_GENERATION_PARAM_META
          const savedParams = normalizeGenerationParams(saved, savedMeta)
          const savedKey = modelConfigKey(saved.provider, saved.selectedModel || '')
          const nextSnapshots = { ...generationParamSnapshotsRef.current, [savedKey]: savedParams }
          generationParamSnapshotsRef.current = nextSnapshots
          setGenerationParamSnapshots(() => nextSnapshots)
          if (generationParamDirtyKeysRef.current[savedKey]) {
            const remaining = { ...generationParamDirtyKeysRef.current }
            delete remaining[savedKey]
            generationParamDirtyKeysRef.current = remaining
            setGenerationParamDirtyKeys(remaining)
          }
          generationParamRequestIdRef.current += 1
          setGenerationParamRemoteStates({})
          setShowProxyPassword(false)
          setRequiresRetest(false)
          toast.success(
            '连接并保存成功',
            `${provider?.label || draft.provider} / ${result.selectedModel} 已设为当前账户默认 AI 服务`,
          )
          if (isDesktopOnboarding) navigate('/dashboard', { replace: true })
          return
        }
        const models = result.models || []
        const verifiedParams = result.generationParams
          ? { ...result.generationParams }
          : { ...draft.generationParams }
        setConfig((current) => ({
          ...current,
          availableModels: models,
          lastTestStatus: 'success',
          lastTestMessage: result.message || null,
          generationParams: verifiedParams,
          generationParamsMeta: result.generationParamsMeta || current.generationParamsMeta,
        }))
        setDraft((current) => ({ ...current, generationParams: verifiedParams }))
        const nextSnapshots = {
          ...generationParamSnapshotsRef.current,
          [activeModelConfigKey]: verifiedParams,
        }
        generationParamSnapshotsRef.current = nextSnapshots
        setGenerationParamSnapshots(() => nextSnapshots)
        setRequiresRetest(false)
        if (result.selectedModel && models.includes(result.selectedModel)) {
          updateDraft('selectedModel', result.selectedModel)
        } else if (draft.selectedModel && models.includes(draft.selectedModel)) {
          // Preserve an explicitly selected model.
        } else if (models.length === 0) {
          setFormError('连接成功，但服务未返回模型列表，请手动填写模型 ID')
        }
      }
    } catch (error: unknown) {
      const message = getErrorMessage(error, '连接失败，请检查地址、密钥和网络设置')
      setTestResult({ success: false, models: [], message })
      setConfig((current) => ({ ...current, lastTestStatus: 'failed', lastTestMessage: message }))
      setRequiresRetest(true)
    } finally {
      setTesting(false)
    }
  }

  const handleModelChange = (selectedModel: string) => {
    if (selectedModel === draft.selectedModel) return
    const nextModelKey = modelConfigKey(draft.provider, selectedModel)
    const snapshots = generationParamSnapshotsRef.current
    const nextParams = isCustomProvider
      ? {}
      : snapshots[nextModelKey]
        ? { ...snapshots[nextModelKey] }
        : initialParamsForUnseenModel(config.generationParamsSupported, generationParamsMeta)
    const nextSnapshots =
      isCustomProvider || !snapshots[nextModelKey]
        ? { ...snapshots, [nextModelKey]: nextParams }
        : snapshots
    generationParamSnapshotsRef.current = nextSnapshots
    setGenerationParamSnapshots(() => nextSnapshots)
    setDraft((current) => ({ ...current, selectedModel, generationParams: nextParams }))
    setRequiresRetest(true)
    setTestResult(null)
    void loadGenerationParamState(draft.provider, selectedModel)
  }

  const handleManualModelChange = (selectedModel: string) => {
    if (selectedModel === draft.selectedModel) {
      updateDraft('selectedModel', selectedModel)
      return
    }
    const nextModelKey = modelConfigKey(draft.provider, selectedModel)
    const snapshots = generationParamSnapshotsRef.current
    const nextParams = isCustomProvider
      ? {}
      : snapshots[nextModelKey]
        ? { ...snapshots[nextModelKey] }
        : initialParamsForUnseenModel(config.generationParamsSupported, generationParamsMeta)
    const nextSnapshots =
      isCustomProvider || !snapshots[nextModelKey]
        ? { ...snapshots, [nextModelKey]: nextParams }
        : snapshots
    generationParamSnapshotsRef.current = nextSnapshots
    setGenerationParamSnapshots(() => nextSnapshots)
    setDraft((current) => ({ ...current, selectedModel, generationParams: nextParams }))
    setRequiresRetest(true)
    setTestResult(null)
    setFormError(null)
  }

  const handleNumericParamChange = (meta: AiGenerationParamMeta, rawValue: string) => {
    const value = coerceGenerationParamValue(rawValue, meta)
    if (value === undefined || typeof value !== 'number') {
      setFormError(`${meta.label || meta.key} 必须是有效数字`)
      return
    }
    if (meta.min !== undefined && value < meta.min) {
      setFormError(`${meta.label || meta.key} 不能小于 ${meta.min}`)
      return
    }
    if (meta.max !== undefined && value > meta.max) {
      setFormError(`${meta.label || meta.key} 不能大于 ${meta.max}`)
      return
    }
    updateGenerationParam(meta.key, value)
  }

  const handleClear = async () => {
    setClearing(true)
    setFormError(null)
    try {
      await aiConfigApi.clear()
      await loadConfig()
      setShowProxyPassword(false)
      toast.success('AI 配置已清除', '当前账户已回退到服务器默认 AI 配置，不会影响登录和非 AI 页面')
    } catch (error: unknown) {
      setFormError(getErrorMessage(error, '配置清除失败，请稍后重试'))
    } finally {
      setClearing(false)
    }
  }

  const handleDismissOnboarding = async () => {
    setFormError(null)
    try {
      await aiConfigApi.dismissOnboarding()
      navigate('/dashboard', { replace: true })
    } catch (error: unknown) {
      setFormError(getErrorMessage(error, '暂时无法跳过配置，请稍后重试'))
    }
  }

  const groupedOptions = useMemo(() => {
    const groups = new Map<AiProviderGroup, AiProviderOption[]>()
    providerOptions.forEach((option) => {
      const group = option.group || 'official'
      const current = groups.get(group) || []
      current.push(option)
      groups.set(group, current)
    })
    return (Object.keys(GROUP_LABELS) as AiProviderGroup[])
      .map((group) => ({ group, options: groups.get(group) || [] }))
      .filter((entry) => entry.options.length > 0)
  }, [providerOptions])

  if (loading) {
    return (
      <div
        className="mx-auto flex w-full max-w-4xl items-center justify-center py-24"
        role="status"
      >
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
        <span className="ml-2 text-sm text-text-secondary">正在加载 AI 配置...</span>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="mx-auto w-full max-w-4xl">
        <Card padding="lg" className="text-center">
          <XCircle className="mx-auto mb-3 h-10 w-10 text-error" />
          <h2 className="text-base font-semibold text-text-primary">AI 配置暂时不可用</h2>
          <p className="mt-2 text-sm text-text-secondary">{loadError}</p>
          <Button variant="outline" size="sm" className="mt-5" onClick={() => void loadConfig()}>
            <RefreshCw className="h-4 w-4" />
            重试
          </Button>
        </Card>
      </div>
    )
  }

  const modelOptions = Array.from(
    new Set([
      ...config.availableModels,
      ...(testResult?.success ? testResult.models : []),
      ...(draft.selectedModel ? [draft.selectedModel] : []),
    ]),
  )

  return (
    <div className="mx-auto w-full max-w-4xl space-y-5 animate-fade-in">
      {isDesktopOnboarding && (
        <section className="flex flex-col gap-3 rounded-lg border border-primary/20 bg-primary/5 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-base font-semibold text-text-primary">连接 AI 服务</h1>
            <p className="mt-1 text-sm text-text-secondary">配置后即可启用资源生成、导学与报告增强功能，也可稍后在设置中完成。</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => void handleDismissOnboarding()}>
            稍后配置
          </Button>
        </section>
      )}
      <Card padding="md">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-primary/10">
              <ServerCog className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-text-primary">AI 服务</h2>
              <p className="mt-1 text-sm text-text-secondary">
                配置后，资源生成、导学和报告等 AI
                功能会统一使用这一套服务。配置仅对当前账户生效，当前账户同一时间只使用一个模型。
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-text-tertiary" aria-live="polite">
            {requiresRetest ? (
              <AlertTriangle className="h-4 w-4 text-warning" />
            ) : config.lastTestStatus === 'success' ? (
              <CheckCircle2 className="h-4 w-4 text-success" />
            ) : config.lastTestStatus === 'failed' ? (
              <XCircle className="h-4 w-4 text-error" />
            ) : (
              <Wifi className="h-4 w-4" />
            )}
            <span>{requiresRetest ? '需重新测试' : statusText(config.lastTestStatus)}</span>
          </div>
        </div>
      </Card>

      <Card padding="lg">
        <div className="space-y-6">
          <div>
            <label
              htmlFor="ai-provider"
              className="mb-1.5 block text-sm font-medium text-text-primary"
            >
              AI 服务来源
            </label>
            <select
              id="ai-provider"
              value={draft.provider}
              onChange={(event) => handleProviderChange(event.target.value)}
              className="h-10 w-full appearance-none rounded-input border border-border bg-bg-secondary px-3 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              {groupedOptions.map(({ group, options }) => (
                <optgroup key={group} label={GROUP_LABELS[group]}>
                  {options.map((option) => (
                    <option
                      key={option.id}
                      value={option.id}
                      disabled={!isProviderImplemented(option)}
                    >
                      {option.label}
                      {!isProviderImplemented(option) ? '（待适配）' : ''}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            {provider?.description && (
              <p className="mt-1.5 text-xs text-text-tertiary">{provider.description}</p>
            )}
          </div>

          {isVertexAi ? (
            <div className="space-y-3">
              <Input
                label="Google Cloud 项目 ID"
                value={draft.projectId}
                onChange={(event) => updateDraft('projectId', event.target.value)}
                placeholder="例如：my-google-cloud-project"
                spellCheck={false}
              />
              <Input
                label="Google Cloud 区域"
                value={draft.location}
                onChange={(event) => updateDraft('location', event.target.value)}
                placeholder="global 或 us-central1"
                spellCheck={false}
              />
              <div>
                <p className="mb-1.5 text-sm font-medium text-text-primary">服务地址</p>
                <div className="flex min-h-10 items-center rounded-input border border-border bg-bg-secondary px-3 font-mono text-sm text-text-secondary break-all">
                  {derivedBaseUrl}
                </div>
              </div>
            </div>
          ) : isBedrock ? (
            <div className="space-y-3">
              <Input
                label="AWS 区域"
                value={draft.region}
                onChange={(event) => updateDraft('region', event.target.value)}
                placeholder="例如：us-east-1"
                spellCheck={false}
              />
              <div>
                <p className="mb-1.5 text-sm font-medium text-text-primary">服务地址</p>
                <div className="flex min-h-10 items-center rounded-input border border-border bg-bg-secondary px-3 font-mono text-sm text-text-secondary break-all">
                  {derivedBaseUrl}
                </div>
              </div>
            </div>
          ) : isBaseUrlEditable ? (
            <div>
              <Input
                label={isAzureOpenAI ? 'Azure OpenAI 资源 Endpoint' : 'API Base URL'}
                name="ai-base-url"
                value={draft.baseUrl}
                onChange={(event) => updateDraft('baseUrl', event.target.value)}
                placeholder={
                  isAzureOpenAI
                    ? 'https://<资源名>.openai.azure.com'
                    : provider?.defaultBaseUrl || 'https://api.example.com/v1'
                }
                spellCheck={false}
                autoComplete="off"
                data-1p-ignore="true"
                data-lpignore="true"
              />
              <p className="mt-1.5 flex items-start gap-1 text-xs text-text-tertiary">
                <Link2 className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
                {isCustomProvider
                  ? '填写兼容 OpenAI 的服务根地址，通常以 /v1 结尾。'
                  : isAzureOpenAI
                    ? '填写 Azure 资源根地址；系统会自动使用 /openai/v1。'
                    : '本地服务地址可按你的本机服务实际端口调整。'}
              </p>
            </div>
          ) : (
            <div>
              <p className="mb-1.5 text-sm font-medium text-text-primary">服务地址</p>
              <div className="flex min-h-10 items-center rounded-input border border-border bg-bg-secondary px-3 font-mono text-sm text-text-secondary break-all">
                {draft.baseUrl || provider?.defaultBaseUrl || '由服务商配置提供'}
              </div>
              <p className="mt-1.5 flex items-start gap-1 text-xs text-text-tertiary">
                <Link2 className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
                此服务使用固定官方地址；如需转发，请使用下方反向代理设置。
              </p>
            </div>
          )}

          {requiresApiKey && (
            <div>
              <label
                htmlFor="ai-api-key"
                className="mb-1.5 block text-sm font-medium text-text-primary"
              >
                {credentialLabel}
              </label>
              <input
                id="ai-api-key"
                name="ai-api-key"
                type="password"
                value={draft.apiKey}
                onChange={(event) => updateDraft('apiKey', event.target.value)}
                placeholder={
                  canReuseApiKey
                    ? `已配置 ${config.apiKeyHint || '（留空保持不变）'}`
                    : config.apiKeyConfigured
                      ? isVertexAi
                        ? '已配置服务账号 JSON；留空保持不变'
                        : '当前为服务器默认密钥；保存账户配置时请重新输入'
                      : credentialPlaceholder
                }
                autoComplete="new-password"
                spellCheck={false}
                data-1p-ignore="true"
                data-lpignore="true"
                data-bwignore="true"
                className="h-10 w-full rounded-input border border-border bg-bg-secondary px-3 font-mono text-sm text-text-primary placeholder:font-sans placeholder:text-text-tertiary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
              <p className="mt-1.5 flex items-start gap-1 text-xs text-text-tertiary">
                <ShieldCheck className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
                {isVertexAi
                  ? '服务账号 JSON 仅加密保存于后端，用于生成短期 Google Cloud 访问令牌，保存后不会回显。'
                  : '仅在提交请求时发送，页面不会持久化明文密钥；只有当前账户已保存的密钥才可留空复用。'}
              </p>
            </div>
          )}

          {!providerImplemented && (
            <div
              role="status"
              className="rounded-lg border border-warning/30 bg-warning-light px-3 py-2.5 text-sm text-warning-dark"
            >
              {provider?.description || '该服务的协议适配尚未完成，暂不能用于 AI 生成功能。'}
            </div>
          )}

          {supportsProxy && (
            <div className="space-y-3 rounded-lg border border-border/70 bg-bg-secondary/30 p-4">
              <div className="flex items-center gap-2">
                <KeyRound className="h-4 w-4 text-text-secondary" />
                <h3 className="text-sm font-medium text-text-primary">反向代理（可选）</h3>
              </div>
              <Input
                label="代理服务器 URL"
                name="ai-proxy-url"
                value={draft.proxyUrl}
                onChange={(event) => updateDraft('proxyUrl', event.target.value)}
                placeholder="https://proxy.example.com"
                spellCheck={false}
                autoComplete="off"
                data-1p-ignore="true"
                data-lpignore="true"
              />
              <div>
                <label
                  htmlFor="ai-proxy-password"
                  className="mb-1.5 block text-sm font-medium text-text-primary"
                >
                  代理密码
                </label>
                <div className="relative">
                  <input
                    id="ai-proxy-password"
                    name="ai-proxy-secret"
                    type={showProxyPassword ? 'text' : 'password'}
                    value={draft.proxyPassword}
                    onChange={(event) => updateDraft('proxyPassword', event.target.value)}
                    placeholder={canReuseProxyPassword ? '已配置（留空保持不变）' : '输入代理密码'}
                    autoComplete="new-password"
                    spellCheck={false}
                    data-1p-ignore="true"
                    data-lpignore="true"
                    data-bwignore="true"
                    className="h-10 w-full rounded-input border border-border bg-bg-card px-3 pr-11 font-mono text-sm text-text-primary placeholder:font-sans placeholder:text-text-tertiary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                  <button
                    type="button"
                    onClick={() => setShowProxyPassword((visible) => !visible)}
                    aria-label={showProxyPassword ? '隐藏代理密码' : '显示代理密码'}
                    title={showProxyPassword ? '隐藏代理密码' : '显示代理密码'}
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1.5 text-text-tertiary hover:bg-bg-tertiary hover:text-text-primary"
                  >
                    {showProxyPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
              <p className="text-xs text-text-tertiary">
                代理密码与 API Key
                分开加密保存；设置代理地址后会优先作为代理访问凭据，自定义服务不启用此项。
              </p>
            </div>
          )}

          <div>
            <div className="mb-1.5 flex items-center justify-between gap-3">
              <label htmlFor="ai-model" className="block text-sm font-medium text-text-primary">
                {modelLabel}
              </label>
              <span className="text-xs text-text-tertiary">同时仅选择一个</span>
            </div>
            {!requiresManualModelEntry && modelOptions.length > 0 ? (
              <select
                id="ai-model"
                value={draft.selectedModel}
                onChange={(event) => handleModelChange(event.target.value)}
                disabled={testing}
                className="h-10 w-full appearance-none rounded-input border border-border bg-bg-secondary px-3 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
              >
                <option value="">请选择模型</option>
                {modelOptions.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            ) : (
              <Input
                id="ai-model"
                value={draft.selectedModel}
                onChange={(event) => handleManualModelChange(event.target.value)}
                onBlur={() => void loadGenerationParamState(draft.provider, draft.selectedModel)}
                placeholder={modelPlaceholder}
                spellCheck={false}
              />
            )}
            <p className="mt-1.5 text-xs text-text-tertiary">
              {isAzureOpenAI
                ? 'Azure 的模型字段必须填写该资源中已创建的部署名称。'
                : isVertexAi
                  ? 'Vertex 使用 Google Cloud 服务账号认证；模型 ID 采用 google/<模型名> 格式。'
                  : '点击“连接并保存”后会刷新列表；某些代理不提供模型列表时可手动填写。'}
            </p>
          </div>

          <div className="border-t border-border pt-4">
            <button
              type="button"
              aria-expanded={isAdvancedOpen}
              onClick={handleAdvancedToggle}
              className="flex w-full items-center justify-between rounded-input px-1 py-2 text-left text-sm font-medium text-text-primary hover:bg-bg-secondary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
            >
              <span className="flex items-center gap-2">
                <ServerCog className="h-4 w-4 text-text-secondary" />
                高级生成参数
                <span className="text-xs font-normal text-text-tertiary">（可选）</span>
              </span>
              {isAdvancedOpen ? (
                <ChevronUp className="h-4 w-4 text-text-secondary" />
              ) : (
                <ChevronDown className="h-4 w-4 text-text-secondary" />
              )}
            </button>
            {isAdvancedOpen && (
              <div className="mt-3 space-y-4 rounded-lg border border-border/70 bg-bg-secondary/30 p-4">
                <div className="flex flex-col gap-1 text-xs text-text-tertiary sm:flex-row sm:items-center sm:justify-between">
                  <span>
                    当前模型：
                    <span className="font-medium text-text-secondary">
                      {draft.selectedModel || '默认模型'}
                    </span>
                  </span>
                  <div className="flex items-center gap-3">
                    <span>修改后必须重新连接并保存</span>
                    {!isCustomProvider &&
                      hasLoadedGenerationParamState &&
                      supportedGenerationParamsMeta.length > 0 && (
                        <button
                          type="button"
                          title="恢复当前模型默认参数"
                          aria-label="恢复当前模型默认参数"
                          onClick={restoreDefaultGenerationParams}
                          className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-xs text-primary hover:bg-primary/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                        >
                          <RefreshCw className="h-3.5 w-3.5" />
                          恢复默认
                        </button>
                      )}
                  </div>
                </div>
                <p className="flex items-start gap-1.5 text-xs text-text-tertiary">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-warning" />
                  仅在了解当前模型参数含义和允许范围时修改；不确定时请保持默认值。
                </p>
                {!hasLoadedGenerationParamState && (
                  <p className="rounded-input border border-warning/30 bg-warning-light px-3 py-2 text-sm text-warning-dark">
                    已切换模型，请先重新连接并保存，以加载该模型可修改的高级参数。
                  </p>
                )}
                {isCustomProvider ? (
                  <div className="space-y-2">
                    <p className="text-xs text-text-tertiary">
                      可按需填写；留空表示使用自定义模型自身的默认值。范围仅作通用参考，请以模型文档为准。
                    </p>
                    {supportedGenerationParamsMeta.map((meta) => {
                      const label = meta.label || meta.key
                      const expanded = Boolean(expandedCustomGenerationParams[meta.key])
                      const value = draft.generationParams[meta.key]
                      const min = meta.min ?? 0
                      const max = meta.max ?? 2
                      const step = meta.step ?? 0.01
                      return (
                        <div
                          key={meta.key}
                          className="rounded-input border border-border/60 bg-bg-secondary/40"
                        >
                          <button
                            type="button"
                            aria-expanded={expanded}
                            onClick={() =>
                              setExpandedCustomGenerationParams((current) => ({
                                ...current,
                                [meta.key]: !current[meta.key],
                              }))
                            }
                            className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left text-sm font-medium text-text-primary hover:bg-bg-secondary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                          >
                            <span>{label}</span>
                            {expanded ? (
                              <ChevronUp className="h-4 w-4 text-text-secondary" />
                            ) : (
                              <ChevronDown className="h-4 w-4 text-text-secondary" />
                            )}
                          </button>
                          {expanded && (
                            <div className="space-y-1.5 border-t border-border/60 px-3 py-3">
                              <input
                                aria-label={label}
                                type="number"
                                min={min}
                                max={max}
                                step={step}
                                value={typeof value === 'number' ? value : ''}
                                placeholder="默认"
                                onChange={(event) => {
                                  if (!event.target.value.trim()) {
                                    removeGenerationParam(meta.key)
                                    return
                                  }
                                  handleNumericParamChange(meta, event.target.value)
                                }}
                                inputMode="decimal"
                                className="h-10 w-full rounded-input border border-border bg-bg-primary px-3 text-sm text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                              />
                              <p className="text-xs text-text-tertiary">
                                范围：{min} - {max}；留空使用模型默认值
                              </p>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                ) : configuredGenerationParams.length > 0 ? (
                  <div className="space-y-4">
                    {configuredGenerationParams.map((meta) => {
                      const value = draft.generationParams[meta.key] ?? getDefaultParamValue(meta)
                      const inputId = `ai-generation-${meta.key.replace(/[^a-zA-Z0-9_-]/g, '-')}`
                      const label = meta.label || meta.key
                      if (meta.type === 'boolean') {
                        return (
                          <label
                            key={meta.key}
                            htmlFor={inputId}
                            className="flex items-center gap-2 text-sm text-text-primary"
                          >
                            <input
                              id={inputId}
                              type="checkbox"
                              checked={value === true}
                              onChange={(event) =>
                                updateGenerationParam(meta.key, event.target.checked)
                              }
                              className="h-4 w-4 rounded border-border text-primary focus:ring-primary/30"
                            />
                            <span>{label}</span>
                            {meta.description && (
                              <span className="text-xs text-text-tertiary">{meta.description}</span>
                            )}
                            <button
                              type="button"
                              aria-label={`删除参数 ${label}`}
                              title={`删除参数 ${label}`}
                              onClick={(event) => {
                                event.preventDefault()
                                removeGenerationParam(meta.key)
                              }}
                              className="ml-auto rounded p-1 text-text-tertiary hover:bg-bg-tertiary hover:text-error"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </label>
                        )
                      }
                      if (meta.type === 'string') {
                        return (
                          <div key={meta.key} className="space-y-1.5">
                            <div className="flex items-center justify-between gap-2">
                              <label
                                htmlFor={inputId}
                                className="text-sm font-medium text-text-primary"
                              >
                                {label}
                              </label>
                              <button
                                type="button"
                                aria-label={`删除参数 ${label}`}
                                title={`删除参数 ${label}`}
                                onClick={() => removeGenerationParam(meta.key)}
                                className="rounded p-1 text-text-tertiary hover:bg-bg-tertiary hover:text-error"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </div>
                            <input
                              id={inputId}
                              type="text"
                              value={typeof value === 'string' ? value : String(value ?? '')}
                              onChange={(event) =>
                                updateGenerationParam(meta.key, event.target.value)
                              }
                              className="h-10 w-full rounded-input border border-border bg-bg-secondary px-3 text-sm text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                            />
                            {meta.description && (
                              <p className="text-xs text-text-tertiary">{meta.description}</p>
                            )}
                          </div>
                        )
                      }
                      const min = meta.min ?? 0
                      const max = meta.max ?? 2
                      const step = meta.step ?? 0.01
                      const numericValue = typeof value === 'number' ? value : Number(value)
                      const safeValue = Number.isFinite(numericValue)
                        ? numericValue
                        : getDefaultParamValue(meta)
                      return (
                        <div key={meta.key} className="space-y-1.5">
                          <div className="flex items-center justify-between gap-2">
                            <label
                              htmlFor={inputId}
                              className="text-sm font-medium text-text-primary"
                            >
                              {label}
                            </label>
                            <button
                              type="button"
                              aria-label={`删除参数 ${label}`}
                              title={`删除参数 ${label}`}
                              onClick={() => removeGenerationParam(meta.key)}
                              className="rounded p-1 text-text-tertiary hover:bg-bg-tertiary hover:text-error"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                          <div className="flex items-center gap-3">
                            <input
                              aria-label={`${label}滑块`}
                              type="range"
                              min={min}
                              max={max}
                              step={step}
                              value={safeValue as number}
                              onChange={(event) =>
                                handleNumericParamChange(meta, event.target.value)
                              }
                              className="min-w-0 flex-1 accent-primary"
                            />
                            <input
                              id={inputId}
                              type="number"
                              min={meta.min}
                              max={meta.max}
                              step={step}
                              value={safeValue as number}
                              onChange={(event) =>
                                handleNumericParamChange(meta, event.target.value)
                              }
                              inputMode="decimal"
                              className="h-10 w-24 rounded-input border border-border bg-bg-secondary px-2 text-right font-mono text-sm text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                            />
                          </div>
                          {meta.description && (
                            <p className="text-xs text-text-tertiary">{meta.description}</p>
                          )}
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-text-tertiary">
                    {!hasLoadedGenerationParamState
                      ? '切换模型后请先重新连接并保存，以加载该模型的参数能力。'
                      : availableGenerationParams.length > 0
                        ? '尚未启用生成参数；可从下方按需添加。'
                        : unsupportedGenerationParams.length > 0
                          ? '当前服务仅使用默认生成参数，不能在此修改。'
                          : '此服务没有可配置的生成参数。'}
                  </p>
                )}
                {hasLoadedGenerationParamState && unsupportedGenerationParams.length > 0 && (
                  <div className="space-y-2 border-t border-border/60 pt-3">
                    <p className="text-xs text-text-tertiary">服务默认值（只读）</p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {unsupportedGenerationParams.map((meta) => {
                        // Unsupported controls are display-only. Ignore any
                        // stale legacy value and show the provider default.
                        const value = getDefaultParamValue(meta)
                        return (
                          <div
                            key={`unsupported-${meta.key}`}
                            className="flex items-center justify-between rounded-input border border-border/60 bg-bg-secondary px-3 py-2 text-sm"
                          >
                            <span className="text-text-secondary">{meta.label || meta.key}</span>
                            <span className="font-mono text-text-tertiary">
                              {formatGenerationParamValue(value)}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
                {!isCustomProvider && (
                  <div className="flex flex-col gap-2 border-t border-border/60 pt-3 sm:flex-row sm:items-center">
                    <select
                      aria-label="添加生成参数"
                      id="ai-generation-param-add"
                      defaultValue=""
                      disabled={availableGenerationParams.length === 0}
                      onChange={(event) => {
                        if (event.target.value) addGenerationParam(event.target.value)
                        event.currentTarget.value = ''
                      }}
                      className="h-9 min-w-0 flex-1 rounded-input border border-border bg-bg-secondary px-2 text-sm text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    >
                      <option value="">
                        {availableGenerationParams.length > 0 ? '添加参数…' : '已添加全部可用参数'}
                      </option>
                      {availableGenerationParams.map((meta) => (
                        <option key={meta.key} value={meta.key}>
                          {meta.label || meta.key}
                        </option>
                      ))}
                    </select>
                    <span className="text-xs text-text-tertiary">
                      参数范围由当前服务返回；超出范围无法连接。
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          {formError && (
            <div
              role="alert"
              className="rounded-lg border border-error/30 bg-error-light px-3 py-2.5 text-sm text-error-dark"
            >
              {formError}
            </div>
          )}
          {testResult && (
            <div
              role="status"
              className={`flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm ${testResult.success ? 'border-success/30 bg-success-light text-success-dark' : 'border-error/30 bg-error-light text-error-dark'}`}
            >
              {testResult.success ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0" />
              ) : (
                <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              )}
              <span>
                {testResult.message ||
                  (testResult.success
                    ? `连接成功，发现 ${testResult.models.length} 个可用模型。`
                    : '连接失败，请检查配置。')}
                {testResult.success &&
                  typeof testResult.latencyMs === 'number' &&
                  `（延迟 ${testResult.latencyMs} ms）`}
              </span>
            </div>
          )}

          <div className="flex flex-col-reverse gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => void handleClear()}
              loading={clearing}
            >
              <Trash2 className="h-4 w-4" />
              清除配置
            </Button>
            <Button
              type="button"
              onClick={() => void handleTest()}
              loading={testing}
              disabled={!providerImplemented}
            >
              <Wifi className="h-4 w-4" />
              {requiresRetest ? '重新连接并保存' : '连接并保存'}
            </Button>
          </div>
        </div>
      </Card>

      <p className="px-1 text-xs leading-relaxed text-text-tertiary">
        安全提示：API Key
        和代理密码只会发送到本系统后端并以加密形式保存。请勿将密钥写入截图、日志、浏览器地址栏或代码仓库。
      </p>

      <Modal
        isOpen={isAdvancedWarningOpen}
        onClose={() => setIsAdvancedWarningOpen(false)}
        maxWidth="max-w-md"
        header={
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-warning" />
            <h2 className="text-base font-semibold text-text-primary">高级参数提醒</h2>
          </div>
        }
        footer={
          <div className="flex justify-end gap-3 px-6 py-4">
            <Button variant="ghost" size="sm" onClick={() => setIsAdvancedWarningOpen(false)}>
              取消
            </Button>
            <Button size="sm" onClick={confirmAdvancedWarning}>
              我知道了，继续
            </Button>
          </div>
        }
      >
        <div className="space-y-3 px-6 py-5 text-sm text-text-secondary">
          <p className="font-medium text-text-primary">
            请不要贸然修改，只有了解参数含义和影响后再调整。
          </p>
          <p>
            高级生成参数由当前 AI
            服务和模型决定。修改后必须重新连接，超出服务允许范围可能导致请求失败；不确定时请保留默认值。
          </p>
        </div>
      </Modal>
    </div>
  )
}
