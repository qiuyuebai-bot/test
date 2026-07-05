# 安全清理项重构方案

## Context

用户在系统性重构任务中选择了"安全清理项"作为起点。测试安全网已就绪（前端 72 + 后端 148 = 220 测试全部通过），可安全进行低风险重构。

本方案目标：**消除死代码、减少重复、修复弃用警告**，严格不改变业务逻辑与运行行为。所有改动均为纯重构（值不变、行为不变），唯一例外是修复前端 `UserRole` 类型缺失 `'enterprise'` 的已有 bug。

诊断阶段识别的 4 项清理：
1. 删除前端死代码 React Query 层
2. 提取重复的 Modal 组件
3. 修复后端 `datetime.utcnow()` 弃用
4. 常量去重（仅安全子集）

---

## 工作项 1：删除 React Query 死代码层

**结论**：React Query 已配置但从未被任何页面/组件/测试调用，是完全死代码。真实数据层是 Zustand store (`src/store/index.ts`) + fetch 客户端 (`src/lib/request.ts`) + `src/api/*.ts` 模块。

**删除文件**（5 个，整文件删除）：
- `src/lib/queryClient.ts`
- `src/hooks/useLearners.ts`
- `src/hooks/useKnowledge.ts`
- `src/hooks/useCore.ts`
- `src/hooks/useAuth.ts`

**编辑文件**（3 个）：
- `src/main.tsx`：移除 `QueryClientProvider` 包裹、`ReactQueryDevtools`、`queryClient` 导入；`<App/>` 直接挂在 `<MemoryRouter>`/`<BrowserRouter>` 下
- `src/hooks/index.ts`：删除 4 行 `export * from './useXxx'`，**保留 `export * from './useTaskSSE'`**（useTaskSSE 被 2 个页面使用，不依赖 React Query）
- `package.json`：删除 `@tanstack/react-query`（dependency）与 `@tanstack/react-query-devtools`（devDependency）两行；随后 `npm install` 重生成 lockfile

**验证**：`npm run typecheck` + `npm test`（72 测试不应受影响，因测试 helper 不引用 React Query）

---

## 工作项 2：提取共享 Modal 组件

**现状**：4 个页面文件中共 8 个 modal，全部使用相同的内联 overlay 模式，无共享 Modal 组件，无 `src/components/ui/` 目录。8 个 modal 行为一致（仅 X 按钮关闭，无 backdrop click、无 Escape、无 ARIA、无 portal、无 focus trap）。

**新建文件**：
- `src/components/Modal.tsx`：共享 Modal 组件

**组件 API**：
```tsx
interface ModalProps {
  isOpen: boolean
  onClose: () => void
  children: React.ReactNode
  maxWidth?: string  // 默认 'max-w-lg'，按调用方传 'max-w-2xl' 等
}
```
组件渲染：overlay `<div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-sm animate-fade-in">` + 内容容器 `<div className={`w-full ${maxWidth} bg-bg-card rounded-2xl shadow-xl overflow-hidden animate-scale-in`}>` + 关闭按钮（右上角 `<button onClick={onClose} className="p-1 hover:bg-bg-secondary rounded-lg transition-colors"><X className="w-5 h-5 text-text-secondary"/></button>`）。

**行为保持**：`closeOnBackdropClick` 和 `closeOnEscape` 默认 `false`，**严格保留当前行为**（仅 X 按钮关闭）。backdrop click、Escape、ARRIA 等留作后续增强，不在本轮。

**重构 8 个 modal**（保持各 modal 的业务 props 与内部逻辑不变，仅替换 overlay 壳）：
- `src/pages/KnowledgeBase.tsx`：DocPreviewModal、TraceabilityModal、UploadModal
- `src/pages/LearnerProfile.tsx`：EditModal、DesensitizationPanel
- `src/pages/MultiAgentVisualization.tsx`：TaskDetailModal（当前用 raw div 而非 `<Card>`，统一为 Modal 组件的默认容器）
- `src/pages/EnterpriseTraining.tsx`：2 个内联条件块（Create 表单、Batch import）改为使用 `<Modal>`

**验证**：`npm test`（MultiAgentVisualization / LearnerProfile / AdaptiveGuidance / LearningReport 页面测试覆盖 modal 渲染）

---

## 工作项 3：修复 datetime 弃用

**关键约束**：所有 SQLAlchemy `DateTime` 列均为 naive（无 `timezone=True`）。直接用 `datetime.now(timezone.utc)`（aware）会与 `func.now()`（naive）混用，导致 `TypeError: can't compare offset-naive and offset-aware datetimes`。采用 **Option A**：naive helper。

**新建文件**：
- `backend/app/utils/datetime.py`：
```python
from datetime import datetime, timezone

def utcnow_naive() -> datetime:
    """UTC 当前时间（naive），替代已弃用的 datetime.utcnow()。保持与 SQLAlchemy naive 列兼容。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)
```

**替换 13 处调用**（全部改为 `from app.utils.datetime import utcnow_naive` 后调用 `utcnow_naive()`）：

`datetime.utcnow()`（6 处）：
- `app/utils/auth.py:89,94`（access token exp/iat）
- `app/utils/auth.py:121,126`（refresh token exp/iat）
- `app/routers/auth.py:136`（user.last_login_at）
- `app/routers/agent.py:488`（task.completed_at）

`datetime.now()` naive（7 处）：
- `app/agents/orchestrator.py:849,945,1046`（task.completed_at/started_at）
- `app/services/knowledge_service.py:214`（doc.indexed_at）
- `app/services/learner_service.py:494,589`（analysis_date/operation_time）
- `app/utils/metrics.py:290`（record_date）

**不改**：模型 `server_default=func.now()`（正确用法）；仅用于显示格式化的 naive `datetime.now()`（report_service.py:494,704 等显示场景，本轮保守不动）。

**验证**：`pytest test_auth test_learner_service test_report_service test_tutoring_service`（覆盖 auth token 生成、learner 时间戳、report 指标）

---

## 工作项 4：常量去重（安全子集）

**范围原则**：仅对已存在的魔法数字/字符串进行**命名提取**（值不变、行为不变）。不包含：page_size 10→20 一致化（属行为变更）、severity/decision 字符串枚举化（爆炸半径过大，留后续）。

### 后端

**新建** `backend/app/constants.py`（单一文件，避免过早拆分）：
```python
# 盲区严重度阈值
BLIND_AREA_HIGH_THRESHOLD = 40
BLIND_AREA_MEDIUM_THRESHOLD = 60

# 自适应决策
ADAPTIVE_DECISION_THRESHOLD = 0.7
BONUS_POINTS_PER_DIFFICULTY = 20

# 难度
MAX_DIFFICULTY_LEVEL = 5
DEFAULT_DIFFICULTY_LEVEL = 3

# 匹配分数阈值
MATCH_SCORE_SUCCESS_THRESHOLD = 70
MATCH_SCORE_GOOD_THRESHOLD = 80
MATCH_SCORE_FAIR_THRESHOLD = 60
```

**提取替换**：
- `report_service.py`：40/60 → 命名常量（2 处：heatmap severity + blind description）
- `diagnosis_agent.py:200-201`：40/60 → 同上
- `learner_service.py:478,407,432`：60/70 → `MATCH_SCORE_*` / 阈值常量
- `tutoring_service.py`：`DECISION_THRESHOLD=0.7` 改为引用常量；message 中 `70%` 改为 `int(ADAPTIVE_DECISION_THRESHOLD*100)`；`*20` → `BONUS_POINTS_PER_DIFFICULTY`；`min(5,...)` → `MAX_DIFFICULTY_LEVEL`
- `tutoring_service.py:396-403` `topic_dimension_map`：提升为模块级常量（仍留在 tutoring_service 或移至 common.py 与 `ABILITY_DIMENSIONS` 同位）
- `report_service.py:153,158,193`：`or 3` → `DEFAULT_DIFFICULTY_LEVEL`
- `common.py:417`：`min(5,...)` → `MAX_DIFFICULTY_LEVEL`
- API prefix：`main.py` / `middleware/prometheus.py` / `rate_limiter.py` / `privacy_service.py` 中裸 `"/api/v1"` → `settings.API_PREFIX`（已存在于 config.py）

### 前端

**新建** `src/lib/constants.ts`：
```typescript
export const SCORE_EXCELLENT_THRESHOLD = 80
export const SCORE_GOOD_THRESHOLD = 60
export const PAGE_SIZE_DEFAULT = 20
export const PAGE_SIZE_LARGE = 50
export const PAGE_SIZE_DASHBOARD = 10
export const API_BASE_URL = '/api/v1'
```

**提取替换**：
- `LearnerProfile.tsx:792,796`、`LearningReport.tsx:175,176,553`、`ResourceGeneration.tsx:250,251`、`SystemTest.tsx:418`、`Deployment.tsx:93`：80/60 → 命名常量
- `Deployment.tsx:225,226`：`'/api/v1/...'` → 使用 `API_BASE_URL`
- pageSize 字面量 → 命名常量（**仅命名当前值，不统一 10/20/50**）

**Bug 修复**（值变更但属修复）：
- `src/types/index.ts:1`：`UserRole` 增加 `'enterprise'`（后端 `UserRoleEnum` 已有 ENTERPRISE，前端类型遗漏）

**验证**：前端 `npm run typecheck && npm test`；后端 `pytest test_report_service test_tutoring_service test_learner_service`

---

## 不在本轮范围（已识别但推迟）

| 项 | 原因 |
|----|------|
| page_size 10 vs 20 一致化 | 行为变更，需产品决策 |
| severity `"high"/"medium"/"low"` 枚举化 | 爆炸半径 ~25 处跨 6 文件，留独立 PR |
| adaptive decision `"simplify"/"advance"/"consolidate"` 枚举化 | ~18 处跨 4 文件，需扩展 enum |
| match-score 权重 0.4/0.3/0.3 提取 | 单文件 1 处，收益低 |
| Modal 增加 backdrop/Escape/ARIA | 行为变更，本轮仅做壳提取 |
| `datetime.now(timezone.utc)` 全量 tz 迁移 | 需 Alembic migration + 列改造，高风险 |

---

## 验证步骤

1. **前端**：`node node_modules/vitest/vitest.mjs run`（72 测试应全绿）
2. **后端**：`venv\Scripts\python.exe -m pytest tests/test_auth.py tests/test_learner_service.py tests/test_privacy_service.py tests/test_training_service.py tests/test_report_service.py tests/test_tutoring_service.py -q`（148 测试应全绿）
3. **类型检查**：`npm run typecheck`
4. **依赖检查**：`npm install` 后确认 lockfile 正常，无残留 React Query 引用
5. **回归确认**：所有改动不触碰业务逻辑/数据接口/UI 交互，仅消除死代码、提取重复、命名常量

## 执行顺序

工作项 1 → 2 → 3 → 4，每项完成后跑对应测试再进入下一项，确保增量可回滚。
