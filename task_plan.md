# 岗位培训闭环修复计划

## Goal
让岗位培训从项目发布、学习者报名、岗位匹配评估、阶段化计划到受权限保护的进度更新形成可验证闭环。

## Next Step
Run the final frontend build and deliver the assessment permission correction.
完成交付前回归检查。

## Current Phase
Phase 5

## Certification Improvement Session

### Goal
Make certification applications and issuance respect learner ownership, assessment ownership, duplicate rules, and certification configuration readiness.

### Scope
- [x] Enforce learner and assessment ownership during application.
- [x] Restrict certification record list/detail access by role.
- [x] Prevent duplicate or already-certified applications.
- [x] Require at least one rule before application and activation.
- [x] Update the certification UI to select a learner and compatible assessment.
- [x] Recheck assessments at approval, support revocation, and expose certificate verification.
- [x] Add backend/frontend regression coverage and run build checks.

### Verification
- Backend certification service and route tests: 33 passed.
- Frontend certification/API tests: 13 passed.
- TypeScript, Python compile, production build, OpenAPI, and diff checks passed.

### Assumptions
- Teachers and administrators may manage certification records for all learners, matching the existing assessment workflow.
- Learners may submit applications for their own learner profile only.
- Existing database fields are reused; this phase does not add migrations.

## Phases

### Phase 1: Requirements & Discovery
- [x] 明确成功标准与实现假设
- [x] 梳理岗位培训前后端流程
- [x] 记录关键缺陷和约束
- **Status:** complete

### Phase 2: Planning & Structure
- [x] 确定项目状态和项目类型兼容策略
- [x] 确定报名、评估匹配和计划阶段接口边界
- [x] 明确测试覆盖范围
- **Status:** complete

### Phase 3: Implementation
- [x] 修复项目发布与项目类型
- [x] 分离查看项目与报名动作
- [x] 增加评估/学习者/项目一致性校验
- [x] 修复计划阶段能力绑定和进度权限
- [x] 传递阶段上下文到资料与练习
- **Status:** complete

### Phase 4: Testing & Verification
- [x] 运行后端培训测试
- [x] 运行前端类型检查和相关测试
- [x] 检查构建与关键流程
- **Status:** complete

### Phase 5: Delivery
- [x] 审查差异和安全边界
- [x] 更新进度记录
- [x] 向用户交付修改结果和剩余风险
- **Status:** complete

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 保留现有表结构，先通过接口和 JSON 计划内容完成闭环 | 降低迁移风险，验证产品流程后再拆分阶段表 |
| 后端做岗位、学习者和权限最终校验 | 前端过滤不能作为安全边界 |
| 项目创建默认保持草稿，发布通过更新状态完成 | 避免创建后隐式开放报名 |
| 兼容已有项目类型值，同时统一新前端提交值 | 避免破坏已有数据 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| React skill 预期路径不存在 | 1 | 使用实际的 react-best-practices skill 路径 |
