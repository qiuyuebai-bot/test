# 安全清理重构 — 剩余工作执行计划

> 本计划承接上一轮已批准的 `safe-cleanup-refactoring.md`，聚焦**尚未完成**的工作项。
> 已完成：工作项 1（React Query 死代码删除）、工作项 2 的 KnowledgeBase 3 个 modal。

## 总览

| 工作项 | 状态 | 剩余动作 |
|---|---|---|
| 1. 删除 React Query 死代码层 | ✅ 已完成 | — |
| 2. 提取共享 Modal 组件 | 🔄 3/8 完成 | 重构剩余 5 个 modal |
| 3. 修复 datetime 弃用 | ⏳ 未启动 | 建 helper + 替换 6 处 `utcnow()` + 审计 `now()` |
| 4. 常量去重（安全子集） | ⏳ 未启动 | 建前后端 constants 文件 + 命名提取 |

---

## 工作项 2：完成 Modal 提取（剩余 5 个）

### 现状
- `src/components/Modal.tsx` 已创建，API：`{ isOpen, onClose, children, maxWidth?, className? }`
- `src/components/index.ts` 已导出 Modal
- KnowledgeBase.tsx 的 3 个 modal 已迁移完成
- MultiAgentVisualization.tsx 已 `import Modal` 但 TaskDetailModal 未替换

### 待改文件与具体操作

#### 2.1 `src/pages/MultiAgentVisualization.tsx` — TaskDetailModal（1 个）
- **当前**（约 113-183 行）：
  ```tsx
  <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-sm animate-fade-in">
    <div className="w-full max-w-2xl bg-bg-card rounded-2xl shadow-xl overflow-hidden animate-scale-in">
      <div className="flex items-center justify-between p-5 border-b border-border">
        ... <button onClick={onClose}>...<X/></button>
      </div>
      ...内容...
    </div>
  </div>
  ```
- **改为**：
  ```tsx
  <Modal isOpen={isOpen} onClose={onClose} maxWidth="max-w-2xl">
    <div className="flex items-center justify-between p-5 border-b border-border">
      ... （移除 close button，Modal 自带）
    </div>
    ...内容...
  </Modal>
  ```
- **注意**：此 modal 用的是裸 `<div>`（非 Card），无需 `className` prop。
- 检查 `X` 图标 import 是否还被其他地方使用，若否则从 import 列表移除。

#### 2.2 `src/pages/LearnerProfile.tsx` — EditModal + DesensitizationPanel（2 个）
- **EditModal**（约 314 行）：
  - 当前：`<Card padding="lg" className="w-full max-w-lg mx-4 animate-scale-in max-h-[90vh] overflow-y-auto">`
  - 改为：`<Modal isOpen={...} onClose={...} maxWidth="max-w-lg" className="p-8 max-h-[90vh] overflow-y-auto">`
  - `className="p-8"` 保留 Card `padding="lg"` 的内边距；`max-h-[90vh] overflow-y-auto` 保留滚动行为
- **DesensitizationPanel**（约 440 行）：
  - 当前：`<Card padding="lg" className="w-full max-w-xl mx-4 animate-scale-in">`
  - 改为：`<Modal isOpen={...} onClose={...} maxWidth="max-w-xl" className="p-8">`
- 添加 `import Modal from '@/components/Modal'`
- 移除每个 modal 内的 close button（Modal 自带）

#### 2.3 `src/pages/EnterpriseTraining.tsx` — 2 个内联 modal（Create 表单 + Batch 导入）
- **Create 表单**（约 462 行）：
  - 当前：`{showCreate && (<div className="fixed inset-0...">...<Card padding="lg" className="w-full max-w-md mx-4 animate-scale-in">...</Card></div>)}`
  - 改为：`{showCreate && (<Modal isOpen={showCreate} onClose={() => setShowCreate(false)} maxWidth="max-w-md" className="p-8">...</Modal>)}`
- **Batch 导入**（约 560 行）：
  - 当前：`{showImport && (<div className="fixed inset-0...">...<Card padding="lg" className="w-full max-w-md mx-4 animate-scale-in">...</Card></div>)}`
  - 改为：`{showImport && (<Modal isOpen={showImport} onClose={() => setShowImport(false)} maxWidth="max-w-md" className="p-8">...</Modal>)}`
- 添加 `import Modal from '@/components/Modal'`
- 移除内联 close button
- 检查 `X` 图标 import 是否还需要

### 验证
```powershell
# 类型检查
node node_modules/typescript/bin/tsc --noEmit
# 单元测试
node node_modules/vitest/vitest.mjs run
# 启动 dev 验证视觉（可选）
# npx vite --host 0.0.0.0
```
预期：72/72 测试通过，typecheck 0 错误。

### 缩进问题
替换后内部内容会深 2 空格。**不单独修缩进**——若 dev 服务器可正常渲染且测试通过，prettier 格式化留作后续可选清理，避免本次改动膨胀。

---

## 工作项 3：修复 datetime 弃用

### 背景
Python 3.12+ 弃用 `datetime.utcnow()`（返回 naive 但语义模糊）。项目所有 SQLAlchemy `DateTime` 列均为 naive，若改用 `datetime.now(timezone.utc)`（aware）会在比较时抛 TypeError。

### 决策（关键）
- **`datetime.utcnow()`（6 处）**：必须替换为 `utcnow_naive()`，行为完全等价（naive UTC）。
- **`datetime.now()`（14 处）**：**不盲目替换**。`datetime.now()` 本身**未弃用**，且返回本地时间；改为 `utcnow_naive()` 会改变语义（本地→UTC），可能破坏显示/日志。
  - 处理方式：逐个审计，**仅当该时间戳会被写入 SQLAlchemy DateTime 列时**才替换为 `utcnow_naive()`；否则保持原样。
  - 若审计后发现全部都是非 DB 用途，则本工作项只替换 6 处 `utcnow()`，不碰 `now()`。

### 待改文件

#### 3.1 新建 `backend/app/utils/datetime.py`
```python
from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """返回 naive UTC datetime，等价于已弃用的 datetime.utcnow()。

    项目所有 SQLAlchemy DateTime 列均为 naive，禁止使用
    datetime.now(timezone.utc)（aware）以防比较时 TypeError。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
```

#### 3.2 替换 6 处 `datetime.utcnow()`
| 文件 | 处数 |
|---|---|
| `backend/app/utils/auth.py` | 4 |
| `backend/app/routers/auth.py` | 1 |
| `backend/app/routers/agent.py` | 1 |

每处：`from app.utils.datetime import utcnow_naive` → `utcnow_na()` 替换 `datetime.utcnow()`。移除原 `datetime.utcnow` 引用（若 `datetime` import 仍被其他用途使用则保留 import）。

#### 3.3 审计 14 处 `datetime.now()`（只读，不改）
逐行确认用途，记录哪些是 DB 写入、哪些是显示/日志。仅对 DB 写入的做替换。
- 重点审计文件：`agents/orchestrator.py`、`services/{knowledge,learner,report}_service.py`、`schemas/response.py`、`routers/core.py`、`utils/metrics.py`

### 验证
```powershell
# Python 语法 + 静态检查
python -m pyflakes backend/app/utils/datetime.py
python -m pyflakes backend/app/utils/auth.py backend/app/routers/auth.py backend/app/routers/agent.py
# 后端测试（排除 ChromaDB 触发的 ONNX 下载）
cd backend
python -m pytest tests/ --ignore=tests/test_api_routes.py --ignore=tests/test_knowledge_service.py -q
```
预期：148 测试通过（已排除的 2 个文件维持原状）。

---

## 工作项 4：常量去重（安全子集）

### 原则
**仅命名提取，不修改值**。把散落的魔法数字集中到 constants 文件并命名，降低认知负担。不改阈值数值、不改业务逻辑。

### 4.1 新建 `backend/app/constants.py`
```python
# 盲区阈值（百分制）
BLIND_AREA_CRITICAL_THRESHOLD = 40
BLIND_AREA_WARNING_THRESHOLD = 60

# 自适应决策
ADAPTIVE_DECISION_THRESHOLD = 0.7

# 难度上限
MAX_DIFFICULTY = 5
DEFAULT_DIFFICULTY = 3
```
然后替换：
- `services/common.py:505` 的 `0.7` → `ADAPTIVE_DECISION_THRESHOLD`
- `services/common.py:417` 的 `min(5, …)` → `min(MAX_DIFFICULTY, …)`
- `services/tutoring_service.py:25` 的局部 `DECISION_THRESHOLD = 0.7` → 改用 import
- `services/tutoring_service.py:285` 的 `min(5, …)` → `min(MAX_DIFFICULTY, …)`
- `services/tutoring_service.py:98` 的 `40`/`60`
- `services/report_service.py` 中 `40`/`60`/`3`（难度默认）按上下文替换
- `services/learner_service.py` 中 `40`/`60`
- `services/knowledge_service.py:169` 的 `40`/`60`

**重要**：替换前必须读每个 call site 确认数字含义与 constants 命名匹配，避免把无关 `40`/`60`（如分页、循环）误替换。仅替换语义为盲区阈值的。

### 4.2 新建 `src/lib/constants.ts`
```typescript
// 评分等级阈值
export const SCORE_EXCELLENT_THRESHOLD = 80
export const SCORE_GOOD_THRESHOLD = 60

// 分页
export const DEFAULT_PAGE_SIZE = 50
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100] as const
```
替换：
- `pages/Deployment.tsx:93`、`LearnerProfile.tsx:792/796`、`LearningReport.tsx:175/176/553`、`ResourceGeneration.tsx:250/251`、`SystemTest.tsx:418` 中的 `80`/`60` → 用上述常量
- pageSize 字面量：仅替换明确为「默认列表页大小 50」的场景（如 `fetchLearners({ page: 1, pageSize: 50 })`），不动分页器组件的选项数组

### 4.3 修复 UserRole bug（原计划附带）
检查 `src/types/index.ts` 或相关类型定义中 `UserRole` 是否缺 `'enterprise'` 枚举值；若缺则补上。

### 验证
```powershell
# 前端
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vitest/vitest.mjs run
# 后端
python -m pyflakes backend/app/constants.py
cd backend && python -m pytest tests/ --ignore=tests/test_api_routes.py --ignore=tests/test_knowledge_service.py -q
```
预期：72 前端 + 148 后端测试全通过。

---

## 执行顺序与回归门禁

1. **工作项 2**（Modal）→ 跑前端 typecheck + 72 测试
2. **工作项 3**（datetime）→ 跑后端 pyflakes + 148 测试
3. **工作项 4**（constants）→ 跑前后端全量 typecheck + 220 测试
4. 全部完成后做一次最终回归：`tsc --noEmit` + `vitest run` + `pytest`

每步失败则回滚该步改动，不继续下一步。

## 不在本次范围
- Modal 的 backdrop 点击关闭、Escape 键、ARIA 属性、focus trap（保持现有行为，deferred）
- 缩进 prettier 全量格式化（避免改动膨胀）
- `datetime.now()` 全量替换为 UTC（仅替换 DB 写入项）
- 硬编码学习者/企业培训业务数据（这是单独的硬约束项，不在安全清理范围）
- 性能基准测试（用户明确「无具体瓶颈」，本次仅安全清理，不做 perf benchmark）

## 假设与决策
- **Modal 行为不变**：不加 backdrop click / Escape / ARIA，仅做 UI 提取，符合"安全清理"定位
- **datetime.now() 不盲改**：避免本地→UTC 语义破坏
- **常量仅命名提取**：不改阈值数值，确保业务行为零变化
- **缩进不单独修**：优先功能正确性，格式化留后续
