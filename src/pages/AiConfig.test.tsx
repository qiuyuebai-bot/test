import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const { aiConfigApiMock } = vi.hoisted(() => ({
  aiConfigApiMock: {
    get: vi.fn(),
    update: vi.fn(),
    test: vi.fn(),
    getGenerationParams: vi.fn(),
    clear: vi.fn(),
  },
}))

vi.mock('@/api', () => ({
  aiConfigApi: aiConfigApiMock,
  AI_PROVIDER_OPTIONS: [],
}))

import AiConfig from './AiConfig'

const baseConfig = {
  configured: true,
  source: 'database',
  provider: 'openai',
  protocol: 'openai_chat',
  baseUrl: 'https://api.openai.com/v1',
  selectedModel: 'gpt-4o',
  availableModels: ['gpt-4o'],
  apiKeyConfigured: true,
  apiKeyHint: 'sk-...1234',
  proxyUrl: '',
  proxyPasswordConfigured: false,
  lastTestStatus: 'never',
  lastTestMessage: null,
  lastTestedAt: null,
  providerOptions: [
    {
      id: 'openai',
      label: 'OpenAI',
      protocol: 'openai_chat',
      group: 'official',
      defaultBaseUrl: 'https://api.openai.com/v1',
      requiresApiKey: true,
      supportsModelsEndpoint: true,
      supportsReverseProxy: true,
      implemented: true,
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
      id: 'custom',
      label: '自定义（兼容 OpenAI）',
      protocol: 'openai_chat',
      group: 'custom',
      defaultBaseUrl: '',
      requiresApiKey: true,
      supportsModelsEndpoint: true,
      supportsReverseProxy: false,
      implemented: true,
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
  ],
}

function renderAiConfig() {
  return render(
    <MemoryRouter>
      <AiConfig />
    </MemoryRouter>,
  )
}

describe('AiConfig', () => {
  beforeEach(() => {
    window.localStorage.clear()
    aiConfigApiMock.get.mockResolvedValue(baseConfig)
    aiConfigApiMock.update.mockResolvedValue(baseConfig)
    aiConfigApiMock.test.mockResolvedValue({
      success: true,
      models: ['gpt-4o', 'gpt-4.1-mini'],
      latencyMs: 124,
      message: '连接成功',
    })
    aiConfigApiMock.getGenerationParams.mockResolvedValue({
      provider: 'openai',
      protocol: 'openai_chat',
      model: 'gpt-4o',
      generationParams: {},
      generationParamsMeta: [],
      generationParamsConfigured: false,
    })
    aiConfigApiMock.clear.mockResolvedValue(null)
  })

  it('uses the server provider options, including dedicated protocol adapters', async () => {
    renderAiConfig()

    await screen.findByRole('heading', { name: 'AI 服务' })

    expect(
      screen.getByText(/配置仅对当前账户生效，当前账户同一时间只使用一个模型/),
    ).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'OpenAI' })).toBeEnabled()
    expect(screen.getByRole('option', { name: 'Claude 官方' })).toBeEnabled()
    expect(screen.queryByRole('option', { name: /DeepSeek/ })).not.toBeInTheDocument()
    expect(screen.getAllByRole('option')[0]).toHaveTextContent('自定义（兼容 OpenAI）')
  })

  it('enables the dedicated Azure, Vertex, and Bedrock setup forms', async () => {
    const user = userEvent.setup()
    renderAiConfig()

    const providerSelect = await screen.findByLabelText('AI 服务来源')
    expect(screen.getByRole('option', { name: 'Azure OpenAI' })).toBeEnabled()
    expect(screen.getByRole('option', { name: 'Google Vertex AI' })).toBeEnabled()
    expect(screen.getByRole('option', { name: 'AWS Bedrock' })).toBeEnabled()

    await user.selectOptions(providerSelect, 'azure_openai')
    expect(screen.getByLabelText('Azure OpenAI 资源 Endpoint')).toBeInTheDocument()
    expect(screen.getByLabelText('Azure 部署名称')).toBeInTheDocument()
    expect(screen.getByLabelText('Azure OpenAI API Key')).toHaveAttribute('type', 'password')

    await user.selectOptions(providerSelect, 'vertex_ai')
    expect(screen.getByLabelText('Google Cloud 项目 ID')).toBeInTheDocument()
    expect(screen.getByLabelText('Google Cloud 区域')).toHaveValue('global')
    expect(screen.getByLabelText('Google Cloud 服务账号 JSON')).toHaveAttribute('type', 'password')
    expect(screen.getByLabelText('Vertex 模型 ID')).toBeInTheDocument()

    await user.selectOptions(providerSelect, 'bedrock')
    expect(screen.getByLabelText('AWS 区域')).toHaveValue('us-east-1')
    expect(screen.getByLabelText('Amazon Bedrock API Key')).toHaveAttribute('type', 'password')
    expect(screen.queryByLabelText('代理服务器 URL')).not.toBeInTheDocument()
  })

  it('sends and rehydrates Vertex-specific configuration without exposing the credential', async () => {
    const user = userEvent.setup()
    const serviceAccountJson = JSON.stringify({
      type: 'service_account',
      client_email: 'vertex@example.iam.gserviceaccount.com',
      private_key: 'placeholder',
      token_uri: 'https://oauth2.googleapis.com/token',
    })
    const savedConfig = {
      ...baseConfig,
      provider: 'vertex_ai',
      protocol: 'vertex_ai',
      baseUrl:
        'https://aiplatform.googleapis.com/v1/projects/vertex-demo-project/locations/global/endpoints/openapi',
      selectedModel: 'google/gemini-2.5-flash',
      availableModels: [],
      apiKeyConfigured: true,
      apiKeyHint: null,
      proxyUrl: '',
      proxyPasswordConfigured: false,
      extraConfig: { projectId: 'vertex-demo-project', location: 'global' },
      lastTestStatus: 'success',
    }
    aiConfigApiMock.get.mockResolvedValueOnce(baseConfig).mockResolvedValueOnce(savedConfig)
    aiConfigApiMock.test.mockResolvedValue({
      success: true,
      models: [],
      selectedModel: 'google/gemini-2.5-flash',
      latencyMs: 124,
      message: '连接成功，配置已保存',
    })
    const view = renderAiConfig()

    const providerSelect = await screen.findByLabelText('AI 服务来源')
    await user.selectOptions(providerSelect, 'vertex_ai')
    await user.type(screen.getByLabelText('Google Cloud 项目 ID'), 'vertex-demo-project')
    await user.clear(screen.getByLabelText('Google Cloud 区域'))
    await user.type(screen.getByLabelText('Google Cloud 区域'), 'global')
    await user.click(screen.getByLabelText('Google Cloud 服务账号 JSON'))
    await user.paste(serviceAccountJson)
    await user.type(screen.getByLabelText('Vertex 模型 ID'), 'google/gemini-2.5-flash')
    await user.click(screen.getByRole('button', { name: /连接并保存/ }))

    await waitFor(() =>
      expect(aiConfigApiMock.test).toHaveBeenCalledWith(
        expect.objectContaining({
          provider: 'vertex_ai',
          protocol: 'vertex_ai',
          baseUrl: '',
          selectedModel: 'google/gemini-2.5-flash',
          extraConfig: { projectId: 'vertex-demo-project', location: 'global' },
        }),
      ),
    )
    expect(aiConfigApiMock.test).toHaveBeenCalledWith(
      expect.objectContaining({ apiKey: serviceAccountJson }),
    )
    await waitFor(() => expect(aiConfigApiMock.get).toHaveBeenCalledTimes(2))
    expect(screen.getByLabelText('Google Cloud 项目 ID')).toHaveValue('vertex-demo-project')
    expect(screen.getByLabelText('Google Cloud 区域')).toHaveValue('global')
    expect(screen.getByLabelText('Vertex 模型 ID')).toHaveValue('google/gemini-2.5-flash')
    expect(screen.getByLabelText('Google Cloud 服务账号 JSON')).toHaveValue('')

    view.unmount()
    aiConfigApiMock.get.mockResolvedValue(savedConfig)
    renderAiConfig()
    expect(await screen.findByLabelText('Google Cloud 项目 ID')).toHaveValue('vertex-demo-project')
  })

  it('keeps the API key masked and opts out of browser credential saving', async () => {
    renderAiConfig()

    const keyInput = await screen.findByLabelText('API Key')
    expect(keyInput).toHaveAttribute('type', 'password')
    expect(keyInput).toHaveAttribute('name', 'ai-api-key')
    expect(keyInput).toHaveValue('')
    expect(keyInput).toHaveAttribute('autocomplete', 'new-password')
    expect(keyInput).toHaveAttribute('data-1p-ignore', 'true')
    expect(keyInput).toHaveAttribute('data-lpignore', 'true')
    expect(keyInput).toHaveAttribute('data-bwignore', 'true')
    expect(screen.getByLabelText('代理密码')).toHaveAttribute('autocomplete', 'new-password')
    expect(screen.queryByRole('button', { name: /API Key/ })).not.toBeInTheDocument()
  })

  it('lets custom providers opt into individual generation parameters', async () => {
    const user = userEvent.setup()
    aiConfigApiMock.get.mockResolvedValue({
      ...baseConfig,
      generationParams: {},
      generationParamsConfigured: false,
      generationParamsSupported: true,
    })
    renderAiConfig()

    const providerSelect = await screen.findByLabelText('AI 服务来源')
    await user.selectOptions(providerSelect, 'custom')
    await user.type(screen.getByLabelText('API Base URL'), 'https://example.com/v1')
    await user.type(screen.getByLabelText('可用模型'), 'custom-model')
    await user.type(screen.getByLabelText('API Key'), 'placeholder-key')
    await user.click(screen.getByRole('button', { name: /高级生成参数/ }))
    await user.click(screen.getByRole('button', { name: '我知道了，继续' }))

    expect(screen.queryByText('服务默认值（只读）')).not.toBeInTheDocument()
    expect(screen.getByText(/留空表示使用自定义模型自身的默认值/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '温度' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByRole('button', { name: 'Top P' })).toHaveAttribute('aria-expanded', 'false')

    await user.click(screen.getByRole('button', { name: '温度' }))
    expect(screen.getByLabelText('温度')).toHaveValue(null)
    expect(screen.getByText('范围：0 - 2；留空使用模型默认值')).toBeInTheDocument()
    await user.type(screen.getByLabelText('温度'), '0.4')
    expect(aiConfigApiMock.test).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: '重新连接并保存' }))
    await waitFor(() => expect(aiConfigApiMock.test).toHaveBeenCalled())
    expect(aiConfigApiMock.test.mock.calls[0][0].generationParams).toEqual({ temperature: 0.4 })
  })

  it('requires acknowledgement before showing editable advanced parameters', async () => {
    const user = userEvent.setup()
    aiConfigApiMock.get.mockResolvedValue({
      ...baseConfig,
      generationParams: {
        temperature: 1,
        frequency_penalty: 0,
        presence_penalty: 0,
        top_p: 1,
      },
      generationParamsMeta: [
        { key: 'temperature', label: '温度', min: 0, max: 2, step: 0.01, defaultValue: 1 },
        {
          key: 'frequency_penalty',
          label: '频率惩罚',
          min: -2,
          max: 2,
          step: 0.01,
          defaultValue: 0,
        },
        {
          key: 'presence_penalty',
          label: '存在惩罚',
          min: -2,
          max: 2,
          step: 0.01,
          defaultValue: 0,
        },
        { key: 'top_p', label: 'Top P', min: 0, max: 1, step: 0.01, defaultValue: 1 },
      ],
      generationParamsSupported: true,
    })
    renderAiConfig()

    await screen.findByRole('heading', { name: 'AI 服务' })
    await user.click(screen.getByRole('button', { name: /高级生成参数/ }))
    expect(screen.getByRole('dialog')).toHaveTextContent(
      '请不要贸然修改，只有了解参数含义和影响后再调整',
    )
    expect(screen.queryByLabelText('温度')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '我知道了，继续' }))
    expect(
      screen.getByText('仅在了解当前模型参数含义和允许范围时修改；不确定时请保持默认值。'),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('温度')).toHaveValue(1)
    expect(screen.getByLabelText('频率惩罚')).toHaveValue(0)
    expect(screen.getByLabelText('存在惩罚')).toHaveValue(0)
    expect(screen.getByLabelText('Top P')).toHaveValue(1)
  })

  it('marks advanced parameter changes for retest and submits them with the connection test', async () => {
    const user = userEvent.setup()
    aiConfigApiMock.get.mockResolvedValue({
      ...baseConfig,
      generationParams: { temperature: 1 },
      generationParamsMeta: [
        { key: 'temperature', label: '温度', min: 0, max: 2, step: 0.01, defaultValue: 1 },
      ],
      generationParamsSupported: true,
    })
    renderAiConfig()

    await screen.findByRole('heading', { name: 'AI 服务' })
    await user.click(screen.getByRole('button', { name: /高级生成参数/ }))
    await user.click(screen.getByRole('button', { name: '我知道了，继续' }))
    await user.clear(screen.getByLabelText('温度'))
    await user.type(screen.getByLabelText('温度'), '0.4')

    expect(screen.getByText('需重新测试')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '重新连接并保存' }))
    await waitFor(() =>
      expect(aiConfigApiMock.test).toHaveBeenCalledWith(
        expect.objectContaining({
          generationParams: expect.objectContaining({ temperature: 0.4 }),
        }),
      ),
    )
  })

  it('restores the current provider/model initial values with one click', async () => {
    const user = userEvent.setup()
    aiConfigApiMock.get.mockResolvedValue({
      ...baseConfig,
      generationParams: { temperature: 0.2, top_p: 0.3 },
      generationParamsConfigured: true,
      generationParamsMeta: [
        {
          key: 'temperature',
          label: '温度',
          min: 0,
          max: 2,
          step: 0.01,
          defaultValue: 0.7,
        },
        { key: 'top_p', label: 'Top P', min: 0, max: 1, step: 0.01, defaultValue: 0.8 },
      ],
    })
    renderAiConfig()

    await screen.findByRole('heading', { name: 'AI 服务' })
    await user.click(screen.getByRole('button', { name: /高级生成参数/ }))
    await user.click(screen.getByRole('button', { name: '我知道了，继续' }))
    expect(screen.getByLabelText('温度')).toHaveValue(0.2)

    await user.click(screen.getByRole('button', { name: '恢复当前模型默认参数' }))
    expect(screen.getByLabelText('温度')).toHaveValue(0.7)
    expect(screen.getByLabelText('Top P')).toHaveValue(0.8)
    expect(screen.getByText('需重新测试')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '重新连接并保存' }))
    await waitFor(() =>
      expect(aiConfigApiMock.test).toHaveBeenCalledWith(
        expect.objectContaining({
          generationParams: { temperature: 0.7, top_p: 0.8 },
        }),
      ),
    )
  })

  it('can remove and restore a parameter without mixing it into another model', async () => {
    const user = userEvent.setup()
    const configWithModels = {
      ...baseConfig,
      availableModels: ['gpt-4o', 'gpt-4.1-mini'],
      generationParams: {
        temperature: 1,
        frequency_penalty: 0,
        presence_penalty: 0,
        top_p: 1,
      },
      generationParamsMeta: [
        { key: 'temperature', label: '温度', min: 0, max: 2, step: 0.01, defaultValue: 1 },
        {
          key: 'frequency_penalty',
          label: '频率惩罚',
          min: -2,
          max: 2,
          step: 0.01,
          defaultValue: 0,
        },
        {
          key: 'presence_penalty',
          label: '存在惩罚',
          min: -2,
          max: 2,
          step: 0.01,
          defaultValue: 0,
        },
        { key: 'top_p', label: 'Top P', min: 0, max: 1, step: 0.01, defaultValue: 1 },
      ],
      generationParamsSupported: true,
    }
    aiConfigApiMock.get.mockResolvedValue(configWithModels)
    renderAiConfig()

    await screen.findByRole('heading', { name: 'AI 服务' })
    await user.click(screen.getByRole('button', { name: /高级生成参数/ }))
    await user.click(screen.getByRole('button', { name: '我知道了，继续' }))
    await user.click(screen.getByRole('button', { name: '删除参数 温度' }))

    expect(screen.queryByLabelText('温度')).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('可用模型'), 'gpt-4.1-mini')
    expect(screen.queryByLabelText('温度')).not.toBeInTheDocument()
    expect(screen.getByLabelText('添加生成参数')).toBeDisabled()

    await user.selectOptions(screen.getByLabelText('可用模型'), 'gpt-4o')
    expect(screen.queryByLabelText('温度')).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('添加生成参数'), 'temperature')
    expect(screen.getByLabelText('温度')).toHaveValue(1)
  })

  it('keeps a manually editable model field for providers without model discovery', async () => {
    aiConfigApiMock.get.mockResolvedValue({
      ...baseConfig,
      provider: 'anthropic',
      protocol: 'anthropic_messages',
      selectedModel: 'claude-sonnet-4-5',
      availableModels: [],
      lastTestStatus: 'success',
    })
    renderAiConfig()

    const model = await screen.findByLabelText('可用模型')
    expect(model.tagName).toBe('INPUT')
    expect(model).toHaveValue('claude-sonnet-4-5')
  })

  it('uses one connection command and requires a key before creating an account configuration', async () => {
    const user = userEvent.setup()
    aiConfigApiMock.get.mockResolvedValue({
      ...baseConfig,
      configured: false,
      source: 'environment',
    })
    renderAiConfig()

    await screen.findByRole('heading', { name: 'AI 服务' })
    expect(screen.queryByRole('button', { name: '保存配置' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '连接并保存' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('请输入 API Key')
    expect(aiConfigApiMock.update).not.toHaveBeenCalled()
    expect(aiConfigApiMock.test).not.toHaveBeenCalled()
  })

  it('fetches models through the backend connection test', async () => {
    const user = userEvent.setup()
    renderAiConfig()

    await screen.findByRole('heading', { name: 'AI 服务' })
    await user.click(screen.getByRole('button', { name: '连接并保存' }))

    await waitFor(() => expect(aiConfigApiMock.test).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(screen.getAllByText(/连接成功/).length).toBeGreaterThan(0))
    expect(screen.getByRole('option', { name: 'gpt-4.1-mini' })).toBeInTheDocument()
  })

  it('rehydrates the account configuration after a successful connection is saved', async () => {
    const user = userEvent.setup()
    const savedConfig = {
      ...baseConfig,
      selectedModel: 'gpt-4.1-mini',
      availableModels: ['gpt-4o', 'gpt-4.1-mini'],
      lastTestStatus: 'success',
    }
    aiConfigApiMock.get.mockResolvedValueOnce(baseConfig).mockResolvedValueOnce(savedConfig)
    aiConfigApiMock.test.mockResolvedValue({
      success: true,
      models: savedConfig.availableModels,
      selectedModel: savedConfig.selectedModel,
      latencyMs: 124,
      message: '连接成功，配置已保存',
    })
    renderAiConfig()

    await screen.findByRole('heading', { name: 'AI 服务' })
    await user.click(screen.getByRole('button', { name: '连接并保存' }))
    await waitFor(() => expect(aiConfigApiMock.test).toHaveBeenCalledTimes(1))

    await waitFor(() => expect(aiConfigApiMock.get).toHaveBeenCalledTimes(2))
    expect(aiConfigApiMock.update).not.toHaveBeenCalled()
    expect(screen.getByLabelText('可用模型')).toHaveValue('gpt-4.1-mini')
  })

  it('keeps a changed model local until a successful connection test', async () => {
    const user = userEvent.setup()
    const configWithModels = {
      ...baseConfig,
      availableModels: ['gpt-4o', 'gpt-4.1-mini'],
    }
    aiConfigApiMock.get.mockResolvedValue(configWithModels)
    const view = renderAiConfig()

    const modelSelect = await screen.findByLabelText('可用模型')
    await user.selectOptions(modelSelect, 'gpt-4.1-mini')

    await waitFor(() => expect(modelSelect).toHaveValue('gpt-4.1-mini'))
    expect(aiConfigApiMock.update).not.toHaveBeenCalled()
    expect(screen.getByText('需重新测试')).toBeInTheDocument()
    expect(modelSelect).toHaveValue('gpt-4.1-mini')

    view.unmount()
    aiConfigApiMock.get.mockResolvedValue({
      ...configWithModels,
      selectedModel: 'gpt-4.1-mini',
    })
    renderAiConfig()

    expect(await screen.findByLabelText('可用模型')).toHaveValue('gpt-4.1-mini')
  })

  it('does not submit untouched parameters when switching models', async () => {
    const user = userEvent.setup()
    const configWithModels = {
      ...baseConfig,
      availableModels: ['gpt-4o', 'gpt-4.1-mini'],
      generationParams: { temperature: 0.4 },
      generationParamsMeta: [
        { key: 'temperature', label: '温度', min: 0, max: 2, step: 0.01, defaultValue: 1 },
      ],
      generationParamsSupported: true,
      generationParamsConfigured: true,
    }
    const savedConfig = {
      ...configWithModels,
      selectedModel: 'gpt-4.1-mini',
      generationParams: {},
      generationParamsConfigured: false,
    }
    aiConfigApiMock.get.mockResolvedValueOnce(configWithModels).mockResolvedValueOnce(savedConfig)
    aiConfigApiMock.test.mockResolvedValue({
      success: true,
      models: savedConfig.availableModels,
      selectedModel: savedConfig.selectedModel,
      latencyMs: 124,
      message: '连接成功，配置已保存',
    })
    renderAiConfig()

    const modelSelect = await screen.findByLabelText('可用模型')
    await user.selectOptions(modelSelect, 'gpt-4.1-mini')
    await user.click(screen.getByRole('button', { name: /高级生成参数/ }))
    await user.click(screen.getByRole('button', { name: '我知道了，继续' }))
    expect(screen.queryByLabelText('温度')).not.toBeInTheDocument()
    expect(
      screen.getByText('切换模型后请先重新连接并保存，以加载该模型的参数能力。'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '重新连接并保存' }))

    await waitFor(() => expect(aiConfigApiMock.test).toHaveBeenCalledTimes(1))
    expect(aiConfigApiMock.test.mock.calls[0][0]).not.toHaveProperty('generationParams')
    expect(await screen.findByLabelText('温度')).toBeInTheDocument()
  })

  it('loads model-specific parameter metadata after switching models', async () => {
    const user = userEvent.setup()
    const configWithModels = {
      ...baseConfig,
      availableModels: ['gpt-4o', 'gpt-4.1-mini'],
      generationParams: { temperature: 1 },
      generationParamsMeta: [
        { key: 'temperature', label: '温度', min: 0, max: 2, step: 0.01, defaultValue: 1 },
        { key: 'top_p', label: 'Top P', min: 0, max: 1, step: 0.01, defaultValue: 1 },
      ],
      generationParamsSupported: true,
    }
    aiConfigApiMock.get.mockResolvedValue(configWithModels)
    aiConfigApiMock.getGenerationParams.mockResolvedValue({
      provider: 'openai',
      protocol: 'openai_chat',
      model: 'gpt-4.1-mini',
      generationParams: { temperature: 0.6 },
      generationParamsMeta: [
        { key: 'temperature', label: '温度', min: 0, max: 1, step: 0.01, defaultValue: 1 },
      ],
      generationParamsConfigured: true,
    })
    renderAiConfig()

    const modelSelect = await screen.findByLabelText('可用模型')
    await user.selectOptions(modelSelect, 'gpt-4.1-mini')
    await waitFor(() =>
      expect(aiConfigApiMock.getGenerationParams).toHaveBeenCalledWith('openai', 'gpt-4.1-mini'),
    )
    await user.click(screen.getByRole('button', { name: /高级生成参数/ }))
    await user.click(screen.getByRole('button', { name: '我知道了，继续' }))

    const temperature = await screen.findByLabelText('温度')
    expect(temperature).toHaveValue(0.6)
    expect(temperature).toHaveAttribute('max', '1')
    expect(screen.queryByLabelText('Top P')).not.toBeInTheDocument()
  })
})
