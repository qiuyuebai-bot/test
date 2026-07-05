# 工作项4 完成计划：常量去重收尾

## 摘要

继续执行已批准的「安全清理项」计划中的工作项4（常量去重）。前序会话已完成：创建 `backend/app/constants.py` 和 `src/lib/constants.ts` 两个常量文件，并在 `learner_service.py`（4处）和 `report_service.py`（7处）完成替换。本计划完成**剩余的后端替换、前端 UserRole 修复、前端评分阈值替换**，并运行完整回归测试。

## 当前状态分析（Phase 1 探索结果）

### 已完成 ✅
- `backend/app/constants.py` 存在，含5个常量
- `src/lib/constants.ts` 存在，含4个常量
- `learner_service.py`：4处替换已完成
- `report_service.py`：7处替换已完成
- `tutoring_service.py`：import 已加（line 18），但2处值未替换
- `common.py`：import 已加（line 16），但1处值未替换

### 待完成 🔄

**后端（3处替换）：**
1. `tutoring_service.py:26` — `DECISION_THRESHOLD = 0.7  # 正确率阈值` → 用 `ADAPTIVE_DECISION_THRESHOLD`
2. `tutoring_service.py:286` — `advanced_difficulty = min(5, current_difficulty + 1)` → 用 `MAX_DIFFICULTY`
3. `common.py:418` — `expected_diff = min(5, max(1, round(avg_ability / 20)))` → 用 `MAX_DIFFICULTY`

**前端 UserRole 修复（1处）：**
- `src/types/index.ts:1` — `UserRole = 'admin' | 'teacher' | 'learner'` 缺少 `'enterprise'`
- 后端 `UserRoleEnum.ENTERPRISE = "enterprise"` 已存在，且有 `is_enterprise()`、`require_enterprise`、`enterprise_name` 字段完整支持
- 前端 `UserRole` 用于 `types/index.ts`、`request.ts`、`ProtectedRoute.tsx`

**前端评分阈值替换（5处）：**
- `LearnerProfile.tsx:786` — `dim.score >= 80 ... dim.score >= 60 ...`
- `LearningReport.tsx:175-176` — `getScoreStatus` 函数 `score >= 80 / score >= 60`
- `LearningReport.tsx:553` — `test.score >= 80 ... test.score >= 60 ...`
- `ResourceGeneration.tsx:250-251` — `getQualityScoreColor` 函数 `score >= 80 / score >= 60`
- `SystemTest.tsx:418` — `rate >= 80`（成功率优秀阈值）

## 关键决策（基于探索结果调整原计划）

### 决策1：Deployment.tsx 不替换 ❌
原计划列出 `Deployment.tsx:93` 需替换 80/60。**实际探索发现** line 91-93 使用的是 `averageAbility < 50 / >= 50 / >= 80`，这是**能力等级分类**（beginner/intermediate/expert），**不是评分阈值**。常量命名为 `SCORE_EXCELLENT_THRESHOLD`，语义不匹配。**跳过此文件**。

### 决策2：common.py:505 不替换 ❌
原计划曾列出此处 `0.7`。**实际探索确认** line 505-507 是 `metrics.average_match_score * 0.7 + match_score * 0.3`——这是**移动平均权重**，非自适应决策阈值。**跳过**（前序会话已决定）。

### 决策3：pageSize 替换跳过 ❌
`DEFAULT_PAGE_SIZE`/`PAGE_SIZE_OPTIONS` 常量已创建但实际使用场景有限：`knowledge.ts:127` 有 `|| 50` 回退，`mockStore.ts:34` 用 `50`（测试文件，改测试风险高）。**本计划不替换 pageSize**，保留常量定义供未来使用。

### 决策4：SystemTest.tsx 的 `rate >= 80` 替换 ✅
虽为成功率而非学习分数，但 `80` 语义上代表"优秀阈值"（≥80% 显示 primary 色），与 `SCORE_EXCELLENT_THRESHOLD` 语义一致。**替换**。

## 实施步骤

### 步骤1：后端剩余替换（2个文件，3处）

**文件 `backend/app/services/tutoring_service.py`：**

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 26 | `DECISION_THRESHOLD = 0.7  # 正确率阈值` | `DECISION_THRESHOLD = ADAPTIVE_DECISION_THRESHOLD  # 正确率阈值` |
| 286 | `advanced_difficulty = min(5, current_difficulty + 1)` | `advanced_difficulty = min(MAX_DIFFICULTY, current_difficulty + 1)` |

**文件 `backend/app/services/common.py`：**

| 行号 | 原代码 | 新代码 |
|------|--------|--------|
| 418 | `expected_diff = min(5, max(1, round(avg_ability / 20)))` | `expected_diff = min(MAX_DIFFICULTY, max(1, round(avg_ability / 20)))` |

**实施注意**：本环境存在 Edit 持久化 bug——某些 Edit 操作返回成功但未实际写入。每次 Edit 后必须用 Grep 验证，未持久化则重新应用。

### 步骤2：前端 UserRole 修复

**文件 `src/types/index.ts`：**

```typescript
// 行1 修改前：
export type UserRole = 'admin' | 'teacher' | 'learner'

// 行1 修改后：
export type UserRole = 'admin' | 'teacher' | 'learner' | 'enterprise'
```

这是纯类型扩展，向后兼容，不影响现有 `'admin'|'teacher'|'learner'` 用户。

### 步骤3：前端评分阈值替换（4个文件，5处）

每个文件需先添加 import，再替换阈值。

**import 语句**（添加到各文件 import 区）：
```typescript
import { SCORE_EXCELLENT_THRESHOLD, SCORE_GOOD_THRESHOLD } from '@/lib/constants'
```

**文件 `src/pages/LearnerProfile.tsx`：**
- 行786：`dim.score >= 80 ? 'text-success' : dim.score >= 60 ? 'text-primary' : 'text-amber-500'`
  → `dim.score >= SCORE_EXCELLENT_THRESHOLD ? 'text-success' : dim.score >= SCORE_GOOD_THRESHOLD ? 'text-primary' : 'text-amber-500'`

**文件 `src/pages/LearningReport.tsx`（2处）：**
- 行175-176（`getScoreStatus` 函数）：
  ```typescript
  if (score >= 80) return { label: '优秀', variant: 'success' }
  if (score >= 60) return { label: '良好', variant: 'warning' }
  ```
  → 用 `SCORE_EXCELLENT_THRESHOLD` / `SCORE_GOOD_THRESHOLD`
- 行553：`test.score >= 80 ? 'bg-success' : test.score >= 60 ? 'bg-primary' : 'bg-amber-500'`
  → 用常量替换

**文件 `src/pages/ResourceGeneration.tsx`：**
- 行250-251（`getQualityScoreColor` 函数）：
  ```typescript
  if (score >= 80) return 'text-success'
  if (score >= 60) return 'text-amber-500'
  ```
  → 用常量替换

**文件 `src/pages/SystemTest.tsx`：**
- 行418：`rate === 100 ? 'text-success' : rate >= 80 ? 'text-primary' : 'text-amber-500'`
  → `rate === 100 ? 'text-success' : rate >= SCORE_EXCELLENT_THRESHOLD ? 'text-primary' : 'text-amber-500'`
  （此处仅替换 `80`，`100` 是满分特殊判断不替换；只导入 `SCORE_EXCELLENT_THRESHOLD`）

### 步骤4：验证

#### 4.1 后端验证
```powershell
# 1. pyflakes 静态检查（确认无未使用 import / 未定义名称）
cd c:\Users\22602\Desktop\新建文件夹\backend
.\venv\Scripts\python.exe -m pyflakes app\constants.py app\services\learner_service.py app\services\report_service.py app\services\tutoring_service.py app\services\common.py

# 2. pytest 后端测试（排除 ChromaDB 和 401 鉴权问题测试）
.\venv\Scripts\python.exe -m pytest tests\ --ignore=tests\test_api_routes.py --ignore=tests\test_knowledge_service.py -q
```
**预期**：pyflakes 零错误；pytest 148 测试通过（基线值，与重构前一致）。

#### 4.2 前端验证
```powershell
cd c:\Users\22602\Desktop\新建文件夹
# 1. TypeScript 类型检查
node node_modules\typescript\bin\tsc --noEmit

# 2. vitest 前端测试
node node_modules\vitest\vitest.mjs run
```
**预期**：tsc 零错误；vitest 72 测试通过（基线值）。

#### 4.3 最终回归测试（工作项4完成）
全部 220 测试通过即视为工作项4完成，整个「安全清理项」计划（4个工作项）全部收尾。

## 假设与约束

1. **常量值不改**：仅做命名提取，所有常量值与原 magic number 完全一致（40/60/0.7/5/3/80/60）
2. **业务逻辑不变**：替换仅为可读性，不修改任何控制流
3. **Edit 持久化 bug**：每次 Edit 后用 Grep 验证，未持久化则重试
4. **测试基线**：72 前端 + 148 后端 = 220 测试，重构后数量与通过率不变
5. **已知预存问题**（非本次引入）：conftest teardown `WinError 32`、test_api_routes 401、ChromaDB ONNX 下载——这些已排除在测试运行外

## 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Edit 未持久化 | 中 | 重试即可 | 每次 Edit 后 Grep 验证 |
| UserRole 扩展破坏现有类型推断 | 低 | 类型扩展向后兼容 | tsc 验证 |
| 常量替换改变语义 | 低 | 值完全一致 | pyflakes + pytest 验证 |
| 测试基线变化 | 低 | 仅替换字面量 | 对比 220 测试基线 |

## 完成标准

- [ ] 后端3处替换完成且 Grep 验证持久化
- [ ] 前端 UserRole 修复完成
- [ ] 前端5处评分阈值替换完成
- [ ] pyflakes 零错误
- [ ] pytest 148 测试通过
- [ ] tsc 零错误
- [ ] vitest 72 测试通过
- [ ] 整个「安全清理项」4个工作项全部完成
