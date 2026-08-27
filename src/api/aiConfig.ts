import { http } from '../lib/request'

/** Protocols supported by the first-party provider adapters. */
export type AiProtocol =
  | 'openai_chat'
  | 'openai_responses'
  | 'anthropic_messages'
  | 'gemini'
  | 'azure_openai'
  | 'vertex_ai'
  | 'aws_bedrock'
  | 'ollama'
  | string

export type AiProviderGroup = 'official' | 'gateway' | 'local' | 'custom'

export type AiGenerationParamValue = number | boolean | string | null

export type AiGenerationParamType = 'number' | 'boolean' | 'string'

/**
 * Metadata for one provider/model generation parameter.  The server may add
 * provider-specific keys, so the client deliberately keeps this shape open.
 */
export interface AiGenerationParamMeta {
  key: string
  label?: string
  type?: AiGenerationParamType
  value?: AiGenerationParamValue
  min?: number
  max?: number
  step?: number
  defaultValue?: AiGenerationParamValue
  default?: AiGenerationParamValue
  supported?: boolean
  description?: string
}

export const DEFAULT_AI_GENERATION_PARAM_META: AiGenerationParamMeta[] = [
  {
    key: 'temperature',
    label: '温度',
    type: 'number',
    min: 0,
    max: 2,
    step: 0.01,
    defaultValue: 1,
    description: '控制输出的随机程度。数值越高，结果越有变化。',
  },
  {
    key: 'frequency_penalty',
    label: '频率惩罚',
    type: 'number',
    min: -2,
    max: 2,
    step: 0.01,
    defaultValue: 0,
    description: '降低重复出现相同词语的概率。',
  },
  {
    key: 'presence_penalty',
    label: '存在惩罚',
    type: 'number',
    min: -2,
    max: 2,
    step: 0.01,
    defaultValue: 0,
    description: '鼓励或抑制引入新主题。',
  },
  {
    key: 'top_p',
    label: 'Top P',
    type: 'number',
    min: 0,
    max: 1,
    step: 0.01,
    defaultValue: 1,
    description: '限制采样候选词范围，通常与温度二选一调整。',
  },
]

export interface AiProviderOption {
  id: string
  label: string
  protocol: AiProtocol
  group?: AiProviderGroup
  defaultBaseUrl?: string
  requiresApiKey?: boolean
  supportsModelsEndpoint?: boolean
  supportsReverseProxy?: boolean
  implemented?: boolean
  defaultModel?: string
  description?: string
}

export interface AiConfig {
  configured?: boolean
  source?: 'database' | 'environment' | string
  provider: string
  protocol: AiProtocol
  baseUrl: string
  selectedModel: string | null
  availableModels: string[]
  apiKeyConfigured: boolean
  apiKeyHint?: string | null
  proxyUrl: string
  proxyPasswordConfigured: boolean
  lastTestStatus?: 'success' | 'failed' | 'never' | string
  lastTestMessage?: string | null
  lastTestedAt?: string | null
  providerOptions?: AiProviderOption[]
  extraConfig?: Record<string, string | number | boolean | null>
  generationParams?: Record<string, AiGenerationParamValue>
  generationParamsMeta?: AiGenerationParamMeta[]
  /** False means the server is showing provider defaults; true means a sparse profile exists. */
  generationParamsConfigured?: boolean
  /** False means an older backend did not advertise the generation fields. */
  generationParamsSupported?: boolean
  onboardingDismissed?: boolean
}

export interface AiGenerationParamsState {
  provider: string
  protocol: AiProtocol
  model: string | null
  generationParams: Record<string, AiGenerationParamValue>
  generationParamsMeta: AiGenerationParamMeta[]
  generationParamsConfigured: boolean
}

export interface AiConfigUpdateRequest {
  provider: string
  protocol?: AiProtocol
  baseUrl?: string
  selectedModel?: string | null
  availableModels?: string[]
  apiKey?: string
  clearApiKey?: boolean
  proxyUrl?: string
  proxyPassword?: string
  clearProxyPassword?: boolean
  extraConfig?: Record<string, string | number | boolean | null>
  generationParams?: Record<string, AiGenerationParamValue>
}

export type AiConfigTestRequest = AiConfigUpdateRequest

export interface AiConfigTestResult {
  success: boolean
  provider?: string
  protocol?: AiProtocol
  models: string[]
  selectedModel?: string | null
  latencyMs?: number | null
  message?: string
  errorCode?: string
  generationParams?: Record<string, AiGenerationParamValue>
  generationParamsMeta?: AiGenerationParamMeta[]
  generationParamsConfigured?: boolean
}

/**
 * Stable client-side fallback catalogue. The server is authoritative whenever
 * it supplies providerOptions. This list only keeps the page operable while an
 * older server is being upgraded and mirrors server-side canonical IDs.
 */
export const AI_PROVIDER_OPTIONS: AiProviderOption[] = [
  {
    id: 'custom',
    label: '自定义（兼容 OpenAI）',
    protocol: 'openai_chat',
    group: 'custom',
    defaultBaseUrl: '',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: false,
  },
  {
    id: 'openai',
    label: 'OpenAI',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://api.openai.com/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    defaultModel: 'gpt-4o',
  },
  {
    id: 'openai_responses',
    label: 'OpenAI Responses',
    protocol: 'openai_responses',
    group: 'official',
    defaultBaseUrl: 'https://api.openai.com/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    defaultModel: 'gpt-4.1',
  },
  {
    id: 'anthropic',
    label: 'Claude 官方',
    protocol: 'anthropic_messages',
    group: 'official',
    defaultBaseUrl: 'https://api.anthropic.com/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: false,
    supportsReverseProxy: true,
    implemented: true,
    defaultModel: 'claude-sonnet-4-5',
  },
  {
    id: 'gemini',
    label: 'Gemini 官方',
    protocol: 'gemini',
    group: 'official',
    defaultBaseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    implemented: true,
    defaultModel: 'gemini-2.0-flash',
  },
  {
    id: 'deepseek',
    label: 'DeepSeek 官方',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://api.deepseek.com',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    defaultModel: 'deepseek-v4-flash',
  },
  {
    id: 'moonshot',
    label: 'Moonshot / Kimi 官方',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://api.moonshot.cn/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    defaultModel: 'kimi-k2.5',
  },
  {
    id: 'moonshot_global',
    label: 'Moonshot / Kimi（国际）',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://api.moonshot.ai/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    defaultModel: 'kimi-k2.5',
  },
  {
    id: 'qwen',
    label: '通义千问 / DashScope',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    defaultModel: 'qwen-plus',
  },
  {
    id: 'zhipu',
    label: '智谱 GLM 官方',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    defaultModel: 'glm-4-plus',
  },
  {
    id: 'zai',
    label: 'Z.ai 官方',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://api.z.ai/api/paas/v4',
    requiresApiKey: true,
    supportsModelsEndpoint: false,
    supportsReverseProxy: true,
    defaultModel: 'glm-4.5',
  },
  {
    id: 'minimax',
    label: 'MiniMax 官方',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://api.minimaxi.com/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: false,
    supportsReverseProxy: true,
    defaultModel: 'MiniMax-M2.7',
  },
  {
    id: 'minimax_global',
    label: 'MiniMax Global',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://api.minimax.io/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: false,
    supportsReverseProxy: true,
    defaultModel: 'MiniMax-M2.7',
  },
  {
    id: 'doubao',
    label: '豆包 / 火山引擎',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    description: '模型名称通常填写火山方舟接入点 ID',
  },
  {
    id: 'baichuan',
    label: '百川智能',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://api.baichuan-ai.com/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    defaultModel: 'Baichuan4',
  },
  {
    id: 'yi',
    label: '零一万物 Yi',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://api.lingyiwanwu.com/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    defaultModel: 'yi-large',
  },
  {
    id: 'stepfun',
    label: '阶跃星辰',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://api.stepfun.com/step_plan/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    defaultModel: 'step-3.5-flash',
  },
  {
    id: 'mistral',
    label: 'Mistral',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://api.mistral.ai/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    defaultModel: 'mistral-large-latest',
  },
  {
    id: 'groq',
    label: 'Groq',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://api.groq.com/openai/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    defaultModel: 'llama-3.3-70b-versatile',
  },
  {
    id: 'grok',
    label: 'xAI / Grok',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://api.x.ai/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
    defaultModel: 'grok-3-mini',
  },
  {
    id: 'perplexity',
    label: 'Perplexity',
    protocol: 'openai_chat',
    group: 'official',
    defaultBaseUrl: 'https://api.perplexity.ai',
    requiresApiKey: true,
    supportsModelsEndpoint: false,
    supportsReverseProxy: true,
    defaultModel: 'sonar',
  },
  {
    id: 'openrouter',
    label: 'OpenRouter',
    protocol: 'openai_chat',
    group: 'gateway',
    defaultBaseUrl: 'https://openrouter.ai/api/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
  },
  {
    id: 'siliconflow',
    label: 'SiliconFlow',
    protocol: 'openai_chat',
    group: 'gateway',
    defaultBaseUrl: 'https://api.siliconflow.cn/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
  },
  {
    id: 'modelscope',
    label: 'ModelScope',
    protocol: 'openai_chat',
    group: 'gateway',
    defaultBaseUrl: 'https://api-inference.modelscope.cn/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
  },
  {
    id: 'aihubmix',
    label: 'AiHubMix',
    protocol: 'openai_chat',
    group: 'gateway',
    defaultBaseUrl: 'https://aihubmix.com/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
  },
  {
    id: 'together',
    label: 'Together AI',
    protocol: 'openai_chat',
    group: 'gateway',
    defaultBaseUrl: 'https://api.together.xyz/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
  },
  {
    id: 'fireworks',
    label: 'Fireworks AI',
    protocol: 'openai_chat',
    group: 'gateway',
    defaultBaseUrl: 'https://api.fireworks.ai/inference/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
  },
  {
    id: 'nvidia',
    label: 'NVIDIA NIM',
    protocol: 'openai_chat',
    group: 'gateway',
    defaultBaseUrl: 'https://integrate.api.nvidia.com/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
  },
  {
    id: 'huggingface',
    label: 'Hugging Face Router',
    protocol: 'openai_chat',
    group: 'gateway',
    defaultBaseUrl: 'https://router.huggingface.co/v1',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: true,
  },
  {
    id: 'ollama',
    label: 'Ollama（本地）',
    protocol: 'ollama',
    group: 'local',
    defaultBaseUrl: 'http://127.0.0.1:11434',
    requiresApiKey: false,
    supportsModelsEndpoint: true,
    supportsReverseProxy: false,
  },
  {
    id: 'lmstudio',
    label: 'LM Studio（本地）',
    protocol: 'openai_chat',
    group: 'local',
    defaultBaseUrl: 'http://localhost:1234/v1',
    requiresApiKey: false,
    supportsModelsEndpoint: true,
    supportsReverseProxy: false,
  },
  {
    id: 'azure_openai',
    label: 'Azure OpenAI',
    protocol: 'azure_openai',
    group: 'official',
    defaultBaseUrl: '',
    requiresApiKey: true,
    supportsModelsEndpoint: false,
    supportsReverseProxy: false,
    implemented: true,
    description: '填写 Azure 资源 Endpoint、API Key 和部署名称',
  },
  {
    id: 'vertex_ai',
    label: 'Google Vertex AI',
    protocol: 'vertex_ai',
    group: 'official',
    defaultBaseUrl: '',
    requiresApiKey: true,
    supportsModelsEndpoint: false,
    supportsReverseProxy: false,
    implemented: true,
    description: '填写 Google Cloud 项目、区域和服务账号 JSON',
  },
  {
    id: 'bedrock',
    label: 'AWS Bedrock',
    protocol: 'aws_bedrock',
    group: 'official',
    defaultBaseUrl: '',
    requiresApiKey: true,
    supportsModelsEndpoint: true,
    supportsReverseProxy: false,
    implemented: true,
    description: '填写 Amazon Bedrock API Key 和 AWS 区域',
  },
]

function normalizeModels(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => {
      if (typeof item === 'string') return item
      if (item && typeof item === 'object' && 'id' in item) {
        const id = (item as { id?: unknown }).id
        return typeof id === 'string' ? id : ''
      }
      return ''
    })
    .filter(Boolean)
}

// Early server builds returned these names in camel case.  Keep accepting
// them, but use the wire names expected by provider adapters everywhere else.
const GENERATION_PARAM_KEY_ALIASES: Record<string, string> = {
  topP: 'top_p',
  frequencyPenalty: 'frequency_penalty',
  presencePenalty: 'presence_penalty',
}

function normalizeGenerationParamKey(key: string): string {
  return GENERATION_PARAM_KEY_ALIASES[key] || key
}

function normalizeGenerationParams(
  value: unknown,
): Record<string, AiGenerationParamValue> | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined

  return Object.entries(value as Record<string, unknown>).reduce<
    Record<string, AiGenerationParamValue>
  >((result, [rawKey, item]) => {
    if (
      typeof item !== 'number' &&
      typeof item !== 'boolean' &&
      typeof item !== 'string' &&
      item !== null
    ) {
      return result
    }
    const key = normalizeGenerationParamKey(rawKey)
    // Prefer an explicitly supplied snake_case value if a legacy response
    // happens to include both spellings.
    if (!(key in result) || rawKey === key) result[key] = item
    return result
  }, {})
}

function normalizeGenerationParamsMeta(value: unknown): AiGenerationParamMeta[] | undefined {
  if (!Array.isArray(value)) return undefined
  return value.reduce<AiGenerationParamMeta[]>((result, item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return result
    const candidate = item as AiGenerationParamMeta
    if (typeof candidate.key !== 'string' || !candidate.key) return result
    result.push({ ...candidate, key: normalizeGenerationParamKey(candidate.key) })
    return result
  }, [])
}

function normalizeConfig(raw: Partial<AiConfig> & Record<string, unknown>): AiConfig {
  const models = normalizeModels(raw.availableModels ?? raw.models)
  const generationParams = normalizeGenerationParams(raw.generationParams)
  const generationParamsMeta = normalizeGenerationParamsMeta(raw.generationParamsMeta)
  const generationParamsConfigured =
    typeof raw.generationParamsConfigured === 'boolean' ? raw.generationParamsConfigured : undefined
  const advertisedGenerationSupport = raw.generationParamsSupported
  return {
    configured: Boolean(raw.configured),
    source: typeof raw.source === 'string' ? raw.source : undefined,
    provider: typeof raw.provider === 'string' ? raw.provider : 'custom',
    protocol: typeof raw.protocol === 'string' ? raw.protocol : 'openai_chat',
    baseUrl: typeof raw.baseUrl === 'string' ? raw.baseUrl : '',
    selectedModel:
      typeof raw.selectedModel === 'string'
        ? raw.selectedModel
        : typeof raw.model === 'string'
          ? raw.model
          : null,
    availableModels: models,
    apiKeyConfigured: Boolean(raw.apiKeyConfigured ?? raw.hasApiKey),
    apiKeyHint: typeof raw.apiKeyHint === 'string' ? raw.apiKeyHint : null,
    proxyUrl: typeof raw.proxyUrl === 'string' ? raw.proxyUrl : '',
    proxyPasswordConfigured: Boolean(raw.proxyPasswordConfigured ?? raw.hasProxyPassword),
    lastTestStatus: typeof raw.lastTestStatus === 'string' ? raw.lastTestStatus : 'never',
    lastTestMessage: typeof raw.lastTestMessage === 'string' ? raw.lastTestMessage : null,
    lastTestedAt: typeof raw.lastTestedAt === 'string' ? raw.lastTestedAt : null,
    providerOptions: Array.isArray(raw.providerOptions)
      ? (raw.providerOptions as AiProviderOption[])
      : Array.isArray(raw.providers)
        ? (raw.providers as AiProviderOption[])
        : undefined,
    extraConfig:
      raw.extraConfig && typeof raw.extraConfig === 'object'
        ? (raw.extraConfig as Record<string, string | number | boolean | null>)
        : undefined,
    generationParams,
    generationParamsMeta,
    generationParamsConfigured,
    generationParamsSupported:
      typeof advertisedGenerationSupport === 'boolean'
        ? advertisedGenerationSupport
        : Object.prototype.hasOwnProperty.call(raw, 'generationParams') ||
          Object.prototype.hasOwnProperty.call(raw, 'generationParamsMeta'),
  }
}

function normalizeTestResult(raw: Record<string, unknown>): AiConfigTestResult {
  return {
    success: Boolean(raw.success),
    provider: typeof raw.provider === 'string' ? raw.provider : undefined,
    protocol: typeof raw.protocol === 'string' ? raw.protocol : undefined,
    models: normalizeModels(raw.models ?? raw.availableModels ?? raw.data),
    selectedModel: typeof raw.selectedModel === 'string' ? raw.selectedModel : null,
    latencyMs: typeof raw.latencyMs === 'number' ? raw.latencyMs : null,
    message: typeof raw.message === 'string' ? raw.message : undefined,
    errorCode: typeof raw.errorCode === 'string' ? raw.errorCode : undefined,
    generationParams: normalizeGenerationParams(raw.generationParams),
    generationParamsMeta: normalizeGenerationParamsMeta(raw.generationParamsMeta),
  }
}

export const aiConfigApi = {
  async get(): Promise<AiConfig> {
    const response = await http.get<Partial<AiConfig> & Record<string, unknown>>('/ai-config')
    return normalizeConfig(response)
  },

  async getGenerationParams(provider: string, model: string): Promise<AiGenerationParamsState> {
    const response = await http.get<Partial<AiGenerationParamsState> & Record<string, unknown>>(
      '/ai-config/generation-params',
      { provider, model },
      { silent: true },
    )
    return {
      provider: typeof response.provider === 'string' ? response.provider : provider,
      protocol: typeof response.protocol === 'string' ? response.protocol : 'openai_chat',
      model: typeof response.model === 'string' ? response.model : null,
      generationParams: normalizeGenerationParams(response.generationParams) || {},
      generationParamsMeta: normalizeGenerationParamsMeta(response.generationParamsMeta) || [],
      generationParamsConfigured: response.generationParamsConfigured === true,
    }
  },

  async update(data: AiConfigUpdateRequest): Promise<AiConfig> {
    const response = await http.put<Partial<AiConfig> & Record<string, unknown>>('/ai-config', data)
    return normalizeConfig(response)
  },

  async test(data: AiConfigTestRequest): Promise<AiConfigTestResult> {
    const response = await http.post<Record<string, unknown>>('/ai-config/test', data, {
      timeout: 30000,
      silent: true,
    })
    return normalizeTestResult(response)
  },

  clear(): Promise<null> {
    return http.delete<null>('/ai-config', undefined, { silent: true })
  },
  dismissOnboarding(): Promise<{ onboardingDismissed: boolean }> {
    return http.post<{ onboardingDismissed: boolean }>('/ai-config/dismiss-onboarding', undefined, {
      silent: true,
    })
  },
}
