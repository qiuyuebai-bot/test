# 新生成专属讲义自动入库实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with checkpoints.

**Goal:** 让上线后新生成且通过质量和元数据校验的专属讲义自动发布到所属领域知识库，历史资源保持不变。

**Architecture:** 在现有 `KnowledgePublicationService` 中增加显式的自动发布入口，创建 `publishing` 状态的系统生成入库记录并复用现有文档索引发布逻辑。资源生成完成路径显式传入自动发布标志，避免历史资源通过旧的同步接口被误处理；前端根据资源质量和入库申请状态展示自动入库状态，保留历史讲义的人工申请入口。

**Tech Stack:** FastAPI、SQLAlchemy、SQLite/PostgreSQL、pytest、React、TypeScript、Vitest。

## Global Constraints

- 仅处理功能上线后新生成的 `resource_type=lecture` 资源；不得批量改写或自动入库历史资源。
- 自动入库必须同时满足 `ready`、`validation_passed=true`、`hallucination_detected=false`、`review_status=approved`、有效标题/领域/正文和受支持格式。
- 同一资源版本和内容哈希必须幂等；`published` 不重复发布，`publish_failed` 仅允许管理员重试。
- 自动发布仍必须经过 `KnowledgeService.process_doc` 索引校验。
- 质量校验失败不得创建可发布的自动入库记录；发布基础设施失败记录为 `publish_failed` 并保留错误信息。

---

### Task 1: 添加自动发布服务入口和严格资格校验

**Files:**
- Modify: `backend/app/domains/knowledge/publication_service.py`
- Test: `backend/tests/test_knowledge_publication.py`

**Interfaces:**
- Produces `KnowledgePublicationService.auto_publish_resource(db: Session, resource_id: int) -> Optional[KnowledgePublicationRequest]`。
- The method creates an immutable snapshot with `submitted_by` set to the learner's user ID, uses status `publishing`, and delegates actual indexing to `_continue_publication`.

- [ ] **Step 1: Write failing tests for automatic qualification and publication**

Add tests that patch `KnowledgeService.process_doc` to return `True` and assert:

```python
request = KnowledgePublicationService.auto_publish_resource(db_session, resource.id)
assert request is not None
assert request.status == PUBLISHED
assert request.reviewed_by is None
assert request.review_note == "系统自动入库"
```

Also add tests asserting that a failed resource, a resource with a blank/placeholder title, and a resource without an industry return `None` and create no publication request. Add a duplicate call assertion that returns the existing published request and leaves one request row.

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run from `backend`:

```powershell
& .\venv\Scripts\python.exe -m pytest tests/test_knowledge_publication.py -k "auto_publish" -q
```

Expected: FAIL because `auto_publish_resource` does not exist.

- [ ] **Step 3: Implement the minimal automatic publication entry point**

In `publication_service.py`:

1. Add `AUTOMATED_PUBLICATION_NOTE = "系统自动入库"`.
2. Add a private validator returning a Chinese diagnostic string or `None`; reject non-lecture, non-latest, non-ready, failed validation, hallucination, blank/placeholder title, blank industry, blank content, and unsupported format.
3. Load `LearnerProfile` for `resource.learner_id`; if no learner or `user_id` exists, return `None` and log the reason.
4. Build `_snapshot` and content hash, then query existing requests for the same resource/version/hash. Return an existing `published`, `publishing`, or `publish_failed` row instead of creating a duplicate.
5. Create a request with `status=PUBLISHING`, `submitted_by=learner.user_id`, `review_note=AUTOMATED_PUBLICATION_NOTE`, commit it, and call `_continue_publication`.
6. Keep `create_request`, administrator approval, and historical synchronization semantics unchanged.

- [ ] **Step 4: Run focused tests and confirm they pass**

```powershell
& .\venv\Scripts\python.exe -m pytest tests/test_knowledge_publication.py -k "auto_publish or lecture_publication" -q
```

Expected: PASS.

- [ ] **Step 5: Commit the service change**

```powershell
git add backend/app/domains/knowledge/publication_service.py backend/tests/test_knowledge_publication.py
git commit -m "feat: add idempotent automatic lecture publication"
```

### Task 2: Trigger automatic publication only from new generation paths

**Files:**
- Modify: `backend/app/agents/task_repository.py`
- Modify: `backend/app/domains/resource/service.py`
- Test: `backend/tests/test_resource_content_integrity.py`
- Test: `backend/tests/test_knowledge_publication.py`

**Interfaces:**
- Consumes `KnowledgePublicationService.auto_publish_resource` from Task 1.
- Preserves `sync_resource_generation_state(db, resource_id)` for historical/legacy request resumption; only new generation paths call the new method.

- [ ] **Step 1: Write failing integration tests for each new-generation path**

Add tests that create a validated lecture through `TaskRepository.save_generation_result`, `ResourceGenerationService._save_resource(..., auto_publish=True)`, and `save_reused_resource_and_complete`, patch document processing, and assert one `published` request is created. Add a regression test that calling `sync_resource_generation_state` for an existing historical resource does not create a request.

- [ ] **Step 2: Run the focused tests and confirm the new integration assertions fail**

```powershell
& .\venv\Scripts\python.exe -m pytest tests/test_resource_content_integrity.py tests/test_knowledge_publication.py -k "automatic or auto_publish or reused" -q
```

Expected: the new assertions fail because generation paths do not trigger automatic publication.

- [ ] **Step 3: Wire the generation paths with exception isolation**

1. In `TaskRepository.save_generation_result`, after the resource transaction commits, call `auto_publish_resource` for the newly saved resource; keep the existing `sync_resource_generation_state` call for any pre-existing requests.
2. In `ResourceGenerationService.generate_all_resources`, pass `auto_publish=True` to `_save_resource`.
3. Add the optional `auto_publish: bool = False` parameter to `_save_resource`; after its resource commit, call the automatic publication entry point only when true and only for lectures. Catch/log publication exceptions so an indexing outage does not turn a successfully generated resource into a generation failure.
4. In `save_reused_resource_and_complete`, call the automatic entry point after commit for the new resource, also behind exception isolation.
5. Do not alter calls that only synchronize existing publication requests, so historical resources remain untouched.

- [ ] **Step 4: Run integration tests and confirm they pass**

```powershell
& .\venv\Scripts\python.exe -m pytest tests/test_resource_content_integrity.py tests/test_knowledge_publication.py -q
```

Expected: PASS, including existing content-integrity and manual approval tests.

- [ ] **Step 5: Commit the generation integration**

```powershell
git add backend/app/agents/task_repository.py backend/app/domains/resource/service.py backend/tests/test_resource_content_integrity.py backend/tests/test_knowledge_publication.py
git commit -m "feat: publish newly generated lectures automatically"
```

### Task 3: Update status presentation and preserve historical manual flow

**Files:**
- Modify: `src/pages/ResourceGeneration.tsx`
- Modify: `src/pages/ResourceReader.tsx`
- Modify: `src/pages/KnowledgeBase.tsx`
- Modify: `src/types/index.ts`
- Test: `src/pages/ResourceReader.test.tsx`

**Interfaces:**
- Consumes the existing resource `reviewStatus`, `status`, `validationPassed`, `hallucinationDetected`, and publication request status.
- Does not change the publication API contract; the manual request endpoint remains available for historical resources.

- [ ] **Step 1: Write failing UI tests for automatic status presentation**

Update the lecture reader fixtures so a ready, validated, approved lecture with a mocked `published` request shows `已入库` and no `申请加入知识库` button. Add a fixture with no request but ready/validated/approved state that shows an automatic-processing message and no manual button. Keep the failed lecture assertion and add a validation-failed label assertion.

- [ ] **Step 2: Run the focused UI tests and confirm the new assertions fail**

Run from the repository root:

```powershell
npm run test -- --run src/pages/ResourceReader.test.tsx
```

Expected: FAIL because the reader still renders the manual application action for eligible lectures and uses the old labels.

- [ ] **Step 3: Implement the minimal UI changes**

1. In `ResourceReader.tsx`, define an `autoEligible` condition for lecture + ready + validated + approved + no hallucination + non-empty content. Hide the manual application action for eligible/processing lectures and show `自动入库中` when no request exists; keep the manual action only for non-eligible historical ready lectures.
2. Rename the reader publication label `pending` to `待处理` and use `publish_failed` error text with its `errorMessage` when present.
3. In `ResourceGeneration.tsx`, render failed resources with `质量校验未通过` instead of `待审核`; keep `approved` as `已通过`.
4. In `KnowledgeBase.tsx`, change the panel copy to explain that new qualifying lectures are automatic and the panel is for historical/manual exceptions; do not render an approval button for `published` or `publish_failed`.
5. Extend the `LearningResource.reviewStatus` union only if the displayed status needs a new stable value; otherwise retain backend-compatible values and derive labels from resource state.

- [ ] **Step 4: Run UI tests, typecheck, and lint**

```powershell
npm run test -- --run src/pages/ResourceReader.test.tsx
npm run typecheck
npm run lint
```

Expected: PASS with no TypeScript or lint errors.

- [ ] **Step 5: Commit the presentation changes**

```powershell
git add src/pages/ResourceGeneration.tsx src/pages/ResourceReader.tsx src/pages/KnowledgeBase.tsx src/types/index.ts src/pages/ResourceReader.test.tsx
git commit -m "feat: show automatic lecture publication states"
```

### Task 4: Full verification and rollout checks

**Files:**
- No source changes expected.

- [ ] **Step 1: Run the complete backend regression suite**

```powershell
cd backend
& .\venv\Scripts\python.exe -m pytest -q
cd ..
```

Expected: all tests pass.

- [ ] **Step 2: Run the complete frontend verification**

```powershell
npm run test -- --run
npm run typecheck
npm run lint
```

Expected: all tests, type checking, and lint pass.

- [ ] **Step 3: Inspect the database without changing historical records**

Verify that a newly generated qualifying lecture has exactly one `knowledge_publication_requests` row with `status='published'`, while an existing historical resource without a request still has no new row.

- [ ] **Step 4: Commit any verification-only documentation if needed**

Do not modify or migrate historical resource rows as part of this feature. Record only test/rollout findings in the final handoff.
