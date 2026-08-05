# DeepSeek 统一内容生成与自适应导学设计

## 状态

- 状态：已获用户确认，待实施
- 日期：2026-08-05
- 范围：统一真实模型接入、关键词题目生成、动态难度和答题建议

## 1. 目标与非目标

### 目标

项目只配置一个 DeepSeek API，题目、学习资源、错题解析、进阶挑战和学习建议均通过同一服务端模型出口生成。

系统应支持：

- 根据不同关键词生成不同知识主题的题目；
- 根据学习者画像、知识盲区和答题历史确定难度；
- 用户答题后生成针对性的解释、资源和学习建议；
- 答题后按结果生成下一道适配题；
- DeepSeek 异常时使用知识库、模板或本地题库继续工作；
- 服务端保存正确答案，前端不接收答案密钥。

### 非目标

- 本阶段不替换现有业务 API 的领域边界；
- 不在前端直接调用 DeepSeek；
- 不引入多模型路由、模型自动竞价或复杂工作流编排；
- 不重构无关的学习资源和用户画像模块。

## 2. 已确认的现状

- [backend/app/utils/llm.py](../../../backend/app/utils/llm.py) 已提供 OpenAI 兼容请求、Prompt 模板调用、熔断和可用性判断。
- [backend/app/services/llm_question_generator.py](../../../backend/app/services/llm_question_generator.py) 已能调用共享的 `LLMGenerator` 生成题目，但题目生成入口仍分散在不同业务路径。
- [backend/app/services/tutoring_service.py](../../../backend/app/services/tutoring_service.py) 已有服务端题目下发、判分、答题记录和自适应决策。
- [src/pages/AdaptiveGuidance.tsx](../../../src/pages/AdaptiveGuidance.tsx) 当前加载已下发题目；页面打开时不会自动生成下一道题。
- 当前自适应决策主要生成简化讲解或进阶挑战，`next_question_difficulty` 目前只记录，尚未驱动下一题生成。

## 3. 总体方案

保留现有资源和导学领域接口，在后端增加一个统一的 `AIContentService`，由它作为所有生成内容的内部门面，并继续通过 `LLMUtil` 发出唯一的外部模型请求。

```text
业务接口
  ├─ 资源生成
  ├─ 导学出题
  └─ 答题与建议
       ↓
AIContentService
       ↓
LLMUtil / PromptManager
       ↓
DeepSeek OpenAI-compatible API
       ↓
JSON 校验、去重、敏感字段隔离
       ↓
业务数据持久化
```

“统一接口”指统一的服务端模型出口，不向前端暴露一个可任意传 Prompt 的通用接口。这样可以保留权限、领域校验和答案隔离。

## 4. DeepSeek 配置

使用环境变量，不把密钥写入代码或提交记录：

```env
OPENAI_API_BASE=https://api.deepseek.com/v1
OPENAI_MODEL_NAME=deepseek-chat
OPENAI_API_KEY=<rotated-secret>
```

`deepseek-chat` 作为默认模型，适用于结构化题目、讲义、解释和建议生成。所有密钥必须在服务端读取，日志中禁止输出密钥、Authorization Header 和完整敏感请求内容。

## 5. 统一内容服务

新增服务入口：

```python
AIContentService.generate(content_type, payload) -> GeneratedContent
```

支持的 `content_type`：

- `question`：导学题目；
- `guide`：实操指南；
- `lecture`：专属讲义；
- `simplified_explanation`：错题简化讲解；
- `advanced_challenge`：进阶挑战；
- `recommendation`：学习建议。

服务内部负责：

1. 选择已登记的 Prompt 模板；
2. 注入关键词、用户画像、知识库片段、难度和历史摘要；
3. 调用 `LLMUtil.call_with_prompt_template`；
4. 解析并校验结构化 JSON；
5. 校验题目知识点、难度、选项和正确答案；
6. 对用户历史题目做去重；
7. 返回统一的生成元数据和失败原因；
8. 按内容类型执行兜底策略。

业务服务不再直接拼接 DeepSeek 请求。

## 6. 关键词与知识库策略

生成请求使用 `target_topic/topic` 作为主关键词，并调用知识库检索相关内容。关键词处理分三步：

1. 规范化：处理同义词和常见缩写，例如 `BP算法` 归一化为 `反向传播算法`；
2. 检索：按规范化关键词检索知识库，并限制参考片段数量和长度；
3. 校验：要求生成题目至少覆盖一个目标知识点，避免题目只包含主题名称但实际跑题。

题目数据增加或统一使用 `knowledge_points` 标签。历史去重使用学习者、主题和题干指纹，避免同一用户短期内拿到重复题。

当知识库无结果时，可以让 DeepSeek 生成通用题，但必须在生成元数据中标记缺少参考资料；若 DeepSeek 失败，则使用主题题库或通用基础题。

## 7. 自适应出题流程

### 首次生成

首次只生成 3 道题，避免预先生成大量固定题目：

- 基础题 1～2 道；
- 当前推荐难度题 1 道；
- 题目写入 `issued_tutoring_questions`；
- 正确答案只保存到 `answer_key`。

### 答题后调整

答题服务先使用服务端答案判分，再调用已有自适应决策：

- 正确：下一题难度提高一级；
- 错误：下一题难度降低一级；
- 连续错误：进入同知识点巩固模式；
- 命中知识盲区：保持或降低难度，并强化基础解释；
- 连续正确：增加综合应用或场景题。

难度限制在 `1～5`。为避免单题造成剧烈波动，建议以最近 3～5 题记录作为辅助判断。

答题接口返回建议内容和下一题所需难度，前端随后请求动态题目接口。这样答题判分和题目生成职责分离，DeepSeek 延迟不会阻塞判分结果。

### 会话结束

每轮导学设置最大题数，例如 10 题。达到上限后返回总结：

- 总体正确率；
- 掌握的知识点；
- 主要薄弱点；
- 推荐复习资源；
- 下一轮建议难度。

## 8. 业务接口调整

继续保留以下领域接口：

```text
POST /resources/generate
POST /tutoring/questions/generate
GET  /tutoring/questions
POST /tutoring/answer
```

### 题目生成

请求继续使用主题、学习者、难度和数量；服务端重新结合画像计算最终难度，不完全信任前端传入的难度。

### 答题响应

增加以下可选字段：

```json
{
  "generated_content": {
    "recommendation": "复习链式法则后再练习梯度计算",
    "key_points": ["链式法则", "梯度传播"],
    "suggested_resources": []
  },
  "next_question_difficulty": 4,
  "session_finished": false
}
```

下一道题仍通过题目生成接口获取，前端只接收公共题目字段，不接收 `answer_key`。

## 9. 统一兜底策略

每种内容都使用以下顺序：

1. DeepSeek 成功且结果通过校验；
2. DeepSeek 短暂失败时重试；
3. 知识库内容 + 服务端模板生成；
4. 主题和难度匹配本地题库；
5. 使用通用基础内容；
6. 返回可理解的降级状态，不让页面进入无响应状态。

所有结果记录 `generation_method`，例如：

```text
deepseek
knowledge_template
deterministic_fallback
seed_bank
```

## 10. 前端行为

[src/pages/AdaptiveGuidance.tsx](../../../src/pages/AdaptiveGuidance.tsx) 调整为：

- 有未作答题目时直接展示；
- 没有题目时显示“生成导学题目”；
- 生成过程中显示加载状态，不重复提交；
- 答题后先展示判分和建议；
- 再根据下一题难度加载新题；
- 题目生成失败时展示兜底状态和重试按钮；
- 达到会话上限时展示学习总结。

关键词优先使用当前学习资源的 `knowledge_topic`；如果没有最近资源，则要求用户输入或选择导学关键词，避免无主题出题。

## 11. 实施阶段

### 阶段一：统一 API 配置和服务出口

- 配置 DeepSeek 环境变量；
- 统一所有模型请求经过 `LLMUtil`；
- 增加 `AIContentService`；
- 统一超时、重试、熔断和日志。

### 阶段二：统一内容协议

- 为题目、讲义、指南、解析、建议定义 JSON 结构；
- 增加字段校验和错误处理；
- 补充题目关键词、知识点和生成方式。

### 阶段三：关键词差异化出题

- 增加关键词规范化；
- 使用知识库检索结果作为参考上下文；
- 增加题目知识点校验和历史去重；
- 调整本地题库的主题标签和匹配逻辑。

### 阶段四：动态难度和答题建议

- 复用现有答题判分和自适应决策；
- 根据答题结果计算下一题难度；
- 使用统一服务生成错题建议和进阶挑战；
- 生成下一道题并持久化。

### 阶段五：前端闭环

- 增加空题生成入口；
- 增加生成中、失败和重试状态；
- 展示学习建议和知识点；
- 支持下一题动态加载和会话总结。

### 阶段六：验证和上线

- 先使用测试 API Key 做真实 API 集成测试；
- 再测试超时、限流、空知识库和非法 JSON；
- 验证答案隔离和权限控制；
- 最后开启真实用户流量。

## 12. 验收标准

- 配置一个 DeepSeek API 后，所有内容类型都能生成；
- `反向传播算法` 和 `Python 列表` 生成的题目知识点明显不同；
- 不同学习者的推荐难度和建议不同；
- 答对、答错、连续答错会产生不同的下一题策略；
- 题目生成失败时仍可完成完整答题流程；
- 前端响应中不存在正确答案字段；
- 题目不会被重复提交或跨用户访问；
- 真实 API 集成测试和现有单元测试均通过。

