# 岗位培训闭环发现

## Requirements
- 修复岗位培训功能，使项目、评估、计划、资源、练习和进度形成可验证闭环。
- 按正确性优先、最小修改原则实施，保留现有项目结构。

## Research Findings
- `TrainingProject` 默认状态为 `draft`，报名只接受 `active` 项目；前端创建后没有发布入口。
- 前端项目类型使用 `onboarding/reskilling/upskilling/certification`，后端枚举使用 `onboard/transfer/upskill/compliance`。
- `LearningPlanTab` 点击查看项目时直接调用报名接口，查看和报名产生副作用。
- 评估记录选择只过滤 `status=completed`，没有匹配项目岗位和报名学习者。
- `generate_plan` 未验证评估记录所属岗位、学习者，也未验证评估记录用户归属。
- AI 计划转换为阶段时把全部 gap 能力绑定到每一个阶段。
- `update_progress` 根据 `plan_id` 修改进度，没有用户/角色权限校验。
- 资料生成和自适应练习目前主要使用岗位名称与学习者 ID，没有计划阶段能力上下文。
- 通用多智能体编排存在，但岗位培训计划生成直接调用 `LLMUtil`，尚未进入培训专用协同流程。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 第一轮不拆分 `plan_content` JSON | 先用阶段级标识和上下文传递验证闭环，避免不必要迁移 |
| 增加独立报名查询接口 | 查看项目不能隐式报名，且需要恢复当前用户/学习者的报名状态 |
| 服务层和路由层分别复用当前角色信息 | 服务层保证业务一致性，路由层提供最小必要权限上下文 |
| 用兼容映射处理已有 project_type 值 | 既修复新建数据，又不破坏历史数据 |

## Resources
- `backend/app/domains/training/service.py`
- `backend/app/domains/training/router.py`
- `backend/app/domains/training/models.py`
- `backend/app/domains/assessment/service.py`
- `src/pages/career-training/LearningPlanTab.tsx`
- `src/pages/career-training/EmbeddedResourceGeneration.tsx`
- `src/pages/career-training/EmbeddedAdaptivePractice.tsx`

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| 计划生成接口同步调用 LLM，可能超时 | 第一轮保留同步接口，仅补充结构校验和错误反馈；异步编排留作下一阶段 |

## Implemented Outcomes

## Assessment Permission Correction
- `/assessments/start` and `/assessments/records/{record_id}/submit` require admin or teacher roles.
- `learner_id` is required by the assessment start schema and is stored on the created record.
- The assessment page provides a staff-only learner selector and sends the selected learner ID when starting an assessment.
- Learners cannot enter scores and their record, detail, and gap queries are scoped to their own user ID.

## Certification Improvement Session
- Certification application currently accepts `learner_id` from the request without checking it against the assessment record or current user.
- Certification record list/detail routes authenticate users but do not enforce ownership.
- A completed assessment can be reused without duplicate checks, and certifications with no rules currently pass automatically.
- The existing frontend loads all assessment records and does not select a learner before applying.

### Resolved
- Application requests now require a learner profile, bind the selected assessment to that profile, and restrict learner self-service to the current account.
- Staff can filter certification records by learner; learner list/detail access is scoped to the current user.
- Missing rules, failing evaluations, duplicate pending applications, reused assessments, and active duplicate certificates are rejected.
- Certification deletion is blocked once records exist, and re-enabling a certification requires at least one rule.
- The certification UI requires staff to select a learner and only offers that learner's completed assessment for the matching position.
- Existing certification creation behavior is preserved; explicit re-enabling requires rules, approval rechecks the current assessment, approved certificates can be revoked, and certificate numbers can be verified publicly.

### Deferred
- Renewal remains a follow-up phase; expired certificates can currently be replaced by a new application based on a newly completed assessment.
- 项目状态现在明确区分草稿和已发布，学习者不能查看或报名草稿项目。
- 学习计划必须基于同岗位、同学习者的已完成评估生成，阶段能力不会重复绑定全部差距项。
- 资源生成和自适应出题共用岗位培训上下文校验，前端传入的项目/报名/计划/阶段标识不能脱离持久化记录使用。
- 仍保留现有同步计划生成接口；若生产环境的评估规模较大，后续可把计划生成改为异步任务并在界面增加生成中状态。
